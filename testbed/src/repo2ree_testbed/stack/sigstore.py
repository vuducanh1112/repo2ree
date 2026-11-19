"""A Sigstore of the run's own, so a showcase signs as an author does, under no real identity and into no public log.

``python -m repo2ree_testbed.stack.sigstore smoke`` starts one, signs a statement, verifies it, and stops it.

Five services, each a container on the network the run's machines share, so ``ree`` on a machine reaches them by
name: Fulcio certifies a key for the identity a token names, under a root this run makes; Tesseract, a CT log,
witnesses each certificate (the signer refuses one it did not); Rekor, on Trillian and MySQL, logs each signature.
The OIDC issuer Fulcio trusts is this run's too: a key, and its discovery documents served by a process here. Tokens
are minted with that key for one test identity, so nobody signs in. What a client needs is one Sigstore client trust
configuration, written beside the descriptor tests read (``LocalSigstore``).

Files reach the containers by ``docker cp``: a machine's daemon may not see this process's paths.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.x509.oid import NameOID
from pydantic import BaseModel, ConfigDict

from repo2ree_testbed.stack.origins import free_port
from repo2ree_testbed.stack.services import workbench_host

IMAGES: Final = {
    "mysql": "gcr.io/trillian-opensource-ci/db_server:v1.8.0",
    "trillian_server": "ghcr.io/sigstore/scaffolding/trillian_log_server:v1.8.0",
    "trillian_signer": "ghcr.io/sigstore/scaffolding/trillian_log_signer:v1.8.0",
    "rekor": "ghcr.io/sigstore/rekor/rekor-server:v1.6.2",
    "tesseract": "ghcr.io/transparency-dev/tesseract/posix:v0.2.0",
    "fulcio": "ghcr.io/sigstore/fulcio:v1.10.1",
}
IDENTITY: Final = "author@repo2ree.invalid"
# Where a test finds the run's Sigstore: the path of its descriptor (LocalSigstore).
SIGSTORE_VARIABLE: Final = "REPO2REE_TEST_SIGSTORE"
# The claim a showcase's author makes, by its published predicate type, as any Sigstore client names it.
AUTHOR_APPROVAL: Final = "https://repo2ree.org/claims/author-approval/v1"
REVIEW: Final = "https://repo2ree.org/claims/review/v1"
_CLIENT_ID: Final = "sigstore"
_CA_PASSWORD: Final = "fulcio"  # noqa: S105 - the run's throwaway CA, as Fulcio's own compose spells it
_MYSQL_DSN: Final = "test:zaphod@tcp({host}:3306)/test?parseTime=true&interpolateParams=true"
_START: Final = "2026-01-01T00:00:00Z"
_READY_SECONDS: Final = 300


class LocalSigstore(BaseModel):
    """What a test needs of the run's Sigstore: its trust configuration, and how to mint a token for the identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    trust_config: Path
    issuer: str
    identity: str
    signing_key: Path

    @classmethod
    def read(cls, descriptor: Path) -> LocalSigstore:
        return cls.model_validate_json(descriptor.read_text(encoding="utf-8"))

    def token(self, lifetime: int = 600) -> str:
        """An OIDC token for the identity, as the issuer Fulcio trusts would mint it."""
        key = serialization.load_pem_private_key(self.signing_key.read_bytes(), password=None)
        assert isinstance(key, ec.EllipticCurvePrivateKey)  # noqa: S101 - the run wrote it so
        now = int(time.time())
        claims = {
            "iss": self.issuer,
            "sub": self.identity,
            "aud": _CLIENT_ID,
            "email": self.identity,
            "email_verified": True,
            "iat": now,
            "nbf": now,
            "exp": now + lifetime,
        }
        header = {"alg": "ES256", "typ": "JWT", "kid": _key_id(key.public_key())}
        signing_input = f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(claims).encode())}"
        r, s = decode_dss_signature(key.sign(signing_input.encode(), ec.ECDSA(hashes.SHA256())))
        return f"{signing_input}.{_b64(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


def local_sigstore() -> LocalSigstore:
    """The run's Sigstore, as the run names it to its tests."""
    descriptor = os.environ.get(SIGSTORE_VARIABLE)
    if not descriptor:
        raise RuntimeError(f"no Sigstore for this run: {SIGSTORE_VARIABLE} is unset (run the tier with --sigstore)")
    return LocalSigstore.read(Path(descriptor))


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _std64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _spki(key: ec.EllipticCurvePublicKey) -> bytes:
    return key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)


def _key_id(key: ec.EllipticCurvePublicKey) -> str:
    return hashlib.sha256(_spki(key)).hexdigest()[:16]


def _jwk(key: ec.EllipticCurvePublicKey) -> dict[str, str]:
    numbers = key.public_numbers()
    return {
        "kty": "EC",
        "crv": "P-256",
        "alg": "ES256",
        "use": "sig",
        "kid": _key_id(key),
        "x": _b64(numbers.x.to_bytes(32, "big")),
        "y": _b64(numbers.y.to_bytes(32, "big")),
    }


def _root_ca() -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    key = ec.generate_private_key(ec.SECP384R1())
    name = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "repo2ree testbed"),
            x509.NameAttribute(NameOID.COMMON_NAME, "repo2ree testbed Fulcio root"),
        ]
    )
    now = datetime.datetime.now(datetime.UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA384())
    )
    return key, certificate


def _http(url: str, timeout: float = 5) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 - the run's own services
        return bytes(response.read())


def _docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=check)


@dataclass
class SigstoreStack:
    """The run's Sigstore: started once, shared by its tests, stopped with the run."""

    directory: Path
    log: Path
    name: str = field(default_factory=lambda: f"repo2ree-sigstore-{uuid.uuid4().hex[:8]}")
    containers: list[str] = field(default_factory=list)
    issuer_process: subprocess.Popen[bytes] | None = None

    def host(self, service: str) -> str:
        return f"{self.name}-{service}"

    def start(self) -> Path:
        """Start every service, wait until each answers, and write the descriptor tests read; its path."""
        self.directory.mkdir(parents=True, exist_ok=True)
        own, network = workbench_host()
        if not network:
            raise RuntimeError("the run's Sigstore joins the machines' Docker network; this process is on none")
        for image in IMAGES.values():
            self._say(f"pulling {image}")
            _docker("pull", "-q", image)
        issuer = self._start_issuer(own)
        root = self._write_root()
        ct_key = self._write_ct_key()
        self._write_fulcio_config(issuer)
        self._run_mysql(network)
        self._run_trillian(network)
        self._run_rekor(network)
        self._run_tesseract(network)
        self._run_fulcio(network)
        rekor_key = serialization.load_pem_public_key(
            self._ready("rekor", f"http://{self.host('rekor')}:3000/api/v1/log/publicKey")
        )
        assert isinstance(rekor_key, ec.EllipticCurvePublicKey)  # noqa: S101 - rekor's memory signer is ECDSA
        trust = self.directory / "trust_config.json"
        trust.write_text(json.dumps(self._trust_config(issuer, root, ct_key.public_key(), rekor_key), indent=2))
        descriptor = self.directory / "sigstore.json"
        local = LocalSigstore(
            trust_config=trust, issuer=issuer, identity=IDENTITY, signing_key=self.directory / "issuer.key"
        )
        descriptor.write_text(local.model_dump_json(indent=2))
        self._say(f"ready: {descriptor}")
        return descriptor

    def stop(self) -> None:
        for container in reversed(self.containers):
            logs = _docker("logs", container, check=False)
            with self.log.open("a", encoding="utf-8") as out:
                out.write(f"---- {container}\n{logs.stdout}{logs.stderr}")
            _docker("rm", "-f", container, check=False)
        self.containers = []
        if self.issuer_process is not None:
            self.issuer_process.terminate()
            self.issuer_process.wait(timeout=10)
            self.issuer_process = None

    # ---- the issuer ------------------------------------------------------------------

    def _start_issuer(self, own: str) -> str:
        key = ec.generate_private_key(ec.SECP256R1())
        (self.directory / "issuer.key").write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
            )
        )
        port = free_port()
        issuer = f"http://{own}:{port}"
        served = self.directory / "issuer"
        (served / ".well-known").mkdir(parents=True, exist_ok=True)
        (served / ".well-known/openid-configuration").write_text(
            json.dumps(
                {
                    "issuer": issuer,
                    "jwks_uri": f"{issuer}/keys",
                    "authorization_endpoint": f"{issuer}/auth",
                    "token_endpoint": f"{issuer}/token",
                    "response_types_supported": ["id_token"],
                    "subject_types_supported": ["public"],
                    "id_token_signing_alg_values_supported": ["ES256"],
                }
            )
        )
        (served / "keys").write_text(json.dumps({"keys": [_jwk(key.public_key())]}))
        with self.log.open("ab") as out:
            self.issuer_process = subprocess.Popen(
                [sys.executable, "-m", "http.server", str(port), "--bind", "0.0.0.0", "--directory", str(served)],  # noqa: S104 - Fulcio reaches it from its container
                stdout=out,
                stderr=subprocess.STDOUT,
            )
        self._ready("issuer", f"http://127.0.0.1:{port}/.well-known/openid-configuration")
        return issuer

    # ---- keys and configuration ------------------------------------------------------

    def _write_root(self) -> x509.Certificate:
        key, certificate = _root_ca()
        (self.directory / "fulcio").mkdir(exist_ok=True)
        (self.directory / "fulcio/root.pem").write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
        (self.directory / "fulcio/root.key").write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.BestAvailableEncryption(_CA_PASSWORD.encode()),
            )
        )
        return certificate

    def _write_ct_key(self) -> ec.EllipticCurvePrivateKey:
        key = ec.generate_private_key(ec.SECP256R1())
        (self.directory / "ctfe").mkdir(exist_ok=True)
        # Tesseract reads an EC key in the SEC 1 encoding only.
        (self.directory / "ctfe/privkey.pem").write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()
            )
        )
        return key

    def _write_fulcio_config(self, issuer: str) -> None:
        (self.directory / "fulcio-config").mkdir(exist_ok=True)
        # Fulcio reads its configuration as JSON first, in JSON's own keys; YAML's would leave it no issuer.
        config = {"OIDCIssuers": {issuer: {"IssuerURL": issuer, "ClientID": _CLIENT_ID, "Type": "email"}}}
        (self.directory / "fulcio-config/config.yaml").write_text(json.dumps(config))

    def _trust_config(
        self,
        issuer: str,
        root: x509.Certificate,
        ct_key: ec.EllipticCurvePublicKey,
        rekor_key: ec.EllipticCurvePublicKey,
    ) -> dict[str, object]:
        def log(url: str, key: ec.EllipticCurvePublicKey) -> dict[str, object]:
            return {
                "baseUrl": url,
                "hashAlgorithm": "SHA2_256",
                "publicKey": {
                    "rawBytes": _std64(_spki(key)),
                    "keyDetails": "PKIX_ECDSA_P256_SHA_256",
                    "validFor": {"start": _START},
                },
                "logId": {"keyId": _std64(hashlib.sha256(_spki(key)).digest())},
            }

        rekor = f"http://{self.host('rekor')}:3000"
        fulcio = f"http://{self.host('fulcio')}:5555"
        service = {"majorApiVersion": 1, "validFor": {"start": _START}, "operator": "repo2ree testbed"}
        return {
            "mediaType": "application/vnd.dev.sigstore.clienttrustconfig.v0.1+json",
            "trustedRoot": {
                "mediaType": "application/vnd.dev.sigstore.trustedroot+json;version=0.1",
                "tlogs": [log(rekor, rekor_key)],
                "certificateAuthorities": [
                    {
                        "subject": {"organization": "repo2ree testbed", "commonName": "repo2ree testbed Fulcio root"},
                        "uri": fulcio,
                        "certChain": {
                            "certificates": [{"rawBytes": _std64(root.public_bytes(serialization.Encoding.DER))}]
                        },
                        "validFor": {"start": _START},
                    }
                ],
                "ctlogs": [log(f"http://{self.host('tesseract')}:6962", ct_key)],
                "timestampAuthorities": [],
            },
            "signingConfig": {
                "mediaType": "application/vnd.dev.sigstore.signingconfig.v0.2+json",
                "caUrls": [{"url": fulcio, **service}],
                "oidcUrls": [{"url": issuer, **service}],
                "rekorTlogUrls": [{"url": rekor, **service}],
                "tsaUrls": [],
                "rekorTlogConfig": {"selector": "ANY"},
                "tsaConfig": {"selector": "ANY"},
            },
        }

    # ---- containers ------------------------------------------------------------------

    def _container(
        self,
        service: str,
        network: str,
        image: str,
        arguments: list[str],
        *,
        environment: dict[str, str] | None = None,
        files: dict[str, str] | None = None,
    ) -> str:
        """Create a service's container, copy its files in, and start it."""
        name = self.host(service)
        create = ["create", "--name", name, "--network", network, "--user", "root"]
        for key, value in (environment or {}).items():
            create += ["--env", f"{key}={value}"]
        _docker(*create, image, *arguments)
        self.containers.append(name)
        for source, target in (files or {}).items():
            _docker("cp", str(self.directory / source), f"{name}:{target}")
        _docker("start", name)
        self._say(f"started {service}")
        return name

    def _run_mysql(self, network: str) -> None:
        name = self._container(
            "mysql",
            network,
            IMAGES["mysql"],
            [],
            environment={
                "MYSQL_ROOT_PASSWORD": "zaphod",
                "MYSQL_DATABASE": "test",
                "MYSQL_USER": "test",
                "MYSQL_PASSWORD": "zaphod",
            },
        )
        deadline = time.monotonic() + _READY_SECONDS
        ping = ["exec", name, "mysqladmin", "-h", "127.0.0.1", "--user=test", "--password=zaphod", "-s", "ping"]
        while _docker(*ping, check=False).returncode != 0:
            if time.monotonic() > deadline:
                raise RuntimeError(f"mysql did not answer within {_READY_SECONDS} s (log: {self.log})")
            time.sleep(2)

    def _run_trillian(self, network: str) -> None:
        dsn = _MYSQL_DSN.format(host=self.host("mysql"))
        common = ["--quota_system=noop", "--storage_system=mysql", f"--mysql_uri={dsn}", "--alsologtostderr"]
        endpoints = ["--rpc_endpoint=0.0.0.0:8090", "--http_endpoint=0.0.0.0:8091"]
        self._container("trillian-server", network, IMAGES["trillian_server"], [*common, *endpoints])
        self._container("trillian-signer", network, IMAGES["trillian_signer"], [*common, *endpoints, "--force_master"])
        self._ready("trillian server", f"http://{self.host('trillian-server')}:8091/healthz")

    def _run_rekor(self, network: str) -> None:
        self._container(
            "rekor",
            network,
            IMAGES["rekor"],
            [
                "serve",
                f"--trillian_log_server.address={self.host('trillian-server')}",
                "--trillian_log_server.port=8090",
                "--rekor_server.address=0.0.0.0",
                "--rekor_server.signer=memory",
                "--search_index.storage_provider=mysql",
                f"--search_index.mysql.dsn={_MYSQL_DSN.format(host=self.host('mysql'))}",
            ],
        )

    def _run_tesseract(self, network: str) -> None:
        self._container(
            "tesseract",
            network,
            IMAGES["tesseract"],
            [
                "--private_key=/etc/ctfe/privkey.pem",
                "--origin=repo2ree-testbed",
                "--storage_dir=/tmp/ctfe",
                "--roots_pem_file=/etc/fulcio/root.pem",
                "--ext_key_usages=CodeSigning",
                "--http_endpoint=0.0.0.0:6962",
            ],
            files={"ctfe": "/etc/ctfe", "fulcio": "/etc/fulcio"},
        )

    def _run_fulcio(self, network: str) -> None:
        self._container(
            "fulcio",
            network,
            IMAGES["fulcio"],
            [
                "serve",
                "--host=0.0.0.0",
                "--port=5555",
                "--grpc-port=5554",
                "--ca=fileca",
                "--fileca-cert=/etc/fulcio/root.pem",
                "--fileca-key=/etc/fulcio/root.key",
                f"--fileca-key-passwd={_CA_PASSWORD}",
                f"--ct-log-url=http://{self.host('tesseract')}:6962",
                "--config-path=/etc/fulcio-config/config.yaml",
            ],
            files={"fulcio": "/etc/fulcio", "fulcio-config": "/etc/fulcio-config"},
        )
        self._ready("fulcio", f"http://{self.host('fulcio')}:5555/healthz")

    # ---- waiting ---------------------------------------------------------------------

    def _ready(self, what: str, url: str) -> bytes:
        deadline = time.monotonic() + _READY_SECONDS
        while True:
            try:
                return _http(url)
            except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
                if time.monotonic() > deadline:
                    raise RuntimeError(f"{what} did not answer at {url} within {_READY_SECONDS} s: {exc}") from exc
                for container in self.containers:
                    state = _docker("inspect", "-f", "{{.State.Status}}", container, check=False).stdout.strip()
                    if state == "exited":
                        logs = _docker("logs", "--tail", "30", container, check=False)
                        raise RuntimeError(f"{container} exited:\n{logs.stdout}{logs.stderr}") from exc
                time.sleep(2)

    def _say(self, message: str) -> None:
        line = f">> sigstore: {message}"
        print(line, flush=True)
        with self.log.open("a", encoding="utf-8") as out:
            out.write(line + "\n")


def sign(
    local: LocalSigstore, name: str, sha256: str, predicate_type: str, *, predicate: dict[str, Any] | None = None
) -> bytes:
    """A Sigstore bundle of an in-toto statement over ``sha256``, signed under the identity, as an author's or a
    reviewer's own Sigstore client signs."""
    from sigstore.dsse import DigestSet, StatementBuilder, Subject  # noqa: PLC0415 - only a signing test needs it
    from sigstore.models import ClientTrustConfig  # noqa: PLC0415
    from sigstore.oidc import IdentityToken  # noqa: PLC0415
    from sigstore.sign import SigningContext  # noqa: PLC0415

    trust = ClientTrustConfig.from_json(local.trust_config.read_text(encoding="utf-8"))
    statement = (
        StatementBuilder()
        .subjects([Subject(name=name, digest=DigestSet({"sha256": sha256}))])
        .predicate_type(predicate_type)
        .predicate(predicate or {})
        .build()
    )
    # Cached, so the certificate's key is the one that signs (sigstore makes a new key per use without it).
    with SigningContext.from_trust_config(trust).signer(IdentityToken(local.token())) as signer:
        return signer.sign_dsse(statement).to_json().encode()


def smoke(directory: Path) -> None:
    """Start the run's Sigstore, sign a statement, verify the bundle against it, and stop it."""
    from sigstore.models import Bundle, ClientTrustConfig  # noqa: PLC0415
    from sigstore.verify import Verifier, policy  # noqa: PLC0415

    stack = SigstoreStack(directory, directory / "sigstore.log")
    try:
        local = LocalSigstore.read(stack.start())
        bundle = sign(local, "smoke", "0" * 64, AUTHOR_APPROVAL)
        (directory / "smoke.sigstore.json").write_bytes(bundle)
        trust = ClientTrustConfig.from_json(local.trust_config.read_text(encoding="utf-8"))
        verifier = Verifier(trusted_root=trust.trusted_root)
        payload_type, _ = verifier.verify_dsse(
            Bundle.from_json(bundle), policy.Identity(identity=local.identity, issuer=local.issuer)
        )
        print(f">> sigstore: signed and verified ({payload_type}) as {local.identity}")
    finally:
        stack.stop()


if __name__ == "__main__":
    smoke(Path(sys.argv[2] if len(sys.argv) > 2 else "test-artifacts/sigstore-smoke").resolve())
