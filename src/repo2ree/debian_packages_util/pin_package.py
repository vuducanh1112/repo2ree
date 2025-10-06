
import datetime
import lzma
from pathlib import Path
import io

import requests
from pydantic import BaseModel
from debian.deb822 import Packages

from repo2ree.dockerfile_utils.os_utils import OSReleaseID, OSReleaseInfo

TMP_CACHE_DIR = Path("/tmp/repo2ree_cache")

###################
# Data Models
###################

class APTPackages(BaseModel):
    packages: dict[str, "APTPackageEntry"]

class APTPackageEntry(BaseModel):
    package: str
    source: str | None = None
    version: str
    installed_size: int | None = None
    maintainer: str | None = None
    architecture: str
    replaces: str | None = None
    provides: str | None = None
    depends: str | None = None
    breaks: str | None = None
    description: str | None = None
    multi_arch: str | None = None
    homepage: str | None = None
    description_md5: str | None = None
    tag: str | None = None
    section: str | None = None
    priority: str | None = None
    filename: str | None = None
    size: int | None = None
    md5sum: str | None = None
    sha1: str | None = None
    sha256: str | None = None

###################
# Main Function
###################

def get_latest_apt_package_version_until_date(
        package_name: str,
        date: datetime.datetime,
        os_release_info: OSReleaseInfo,
        architecture: str,
        packages_file_cache_location: Path = TMP_CACHE_DIR,
        ) -> str:

    version = ""

    package_list_str = get_or_download_packages_file(
        os_release_id=os_release_info.id,
        version_code_name=os_release_info.version_code_name,
        architecture=architecture,
        target_date=date,
        cache_location=packages_file_cache_location,
    )
    
    apt_packages = parse_packages_file(package_list_str)
    if package_name not in apt_packages.packages:
        Path("debug_packages_file.json").write_text(APTPackages.model_dump_json(apt_packages, indent=2))
        raise ValueError(f"Package '{package_name}' not found in the Packages file for {os_release_info.id.value} {os_release_info.version_code_name} on {date.isoformat()}")

    version = apt_packages.packages[package_name].version
        
    return version

###################
# Impure Functions
###################

def get_or_download_packages_file(
        os_release_id: OSReleaseID,
        version_code_name: str, 
        architecture: str, 
        target_date: datetime.datetime, 
        cache_location: Path,
        ) -> str:
    
    snapshot_timestamp = target_date.strftime("%Y%m%dT%H%M%SZ")
    snapshot_archive_base = ""
    snapshot_url = ""

    match os_release_id:
        case OSReleaseID.DEBIAN:

            snapshot_archive_base = "http://snapshot.debian.org/archive/"
            #TODO security main, updates main, backports main
            snapshot_url = f"{snapshot_archive_base}debian/{snapshot_timestamp}/dists/{version_code_name}/main/binary-{architecture}/Packages.xz"

        case OSReleaseID.UBUNTU:
            # TODO ubuntu >= 24.04 has new format
            match architecture:
                case "amd64" | "i386":
                    snapshot_archive_base = "http://archive.ubuntu.com/"
                    snapshot_url = f"{snapshot_archive_base}ubuntu/dists/{version_code_name}/main/binary-{architecture}/Packages.xz"
                case "arm64" | "armhf" | "ppc64el" | "s390x" | "riscv64":
                    snapshot_archive_base = "http://ports.ubuntu.com/"
                    snapshot_url = f"{snapshot_archive_base}dists/{version_code_name}/main/binary-{architecture}/Packages.xz"
                case _:
                    raise ValueError(f"Unsupported architecture for Ubuntu: {architecture}")
        case _:
            raise ValueError(f"The OS does not use apt: {os_release_id}")

    file_path = cache_location / snapshot_url.lstrip(snapshot_archive_base)
    if not file_path.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading Packages file to: {file_path}")
        response = requests.get(snapshot_url)
        if response.status_code != 200:
            raise ValueError(f"Failed to download Packages file from {snapshot_url}: {response.status_code}")
        with open(file_path, 'wb') as f:
            f.write(response.content)
    else:
        print(f"Using cached Packages file: {file_path}")

    with open(file_path, 'rb') as f:
        compressed_data = f.read()
    decompressed_data = lzma.decompress(compressed_data)
    packages = decompressed_data.decode('utf-8')

    return packages

###################
# Pure Functions
###################

def parse_packages_file(packages_file_str: str) -> APTPackages:

    apt_packages = {}

    with io.StringIO(packages_file_str) as packages_file:
        
        for package_record in Packages.iter_paragraphs(packages_file):
            package_name = package_record["Package"]
            apt_packages[package_name] = APTPackageEntry(**{key.lower(): value for key, value in package_record.items()})
    
    return APTPackages(packages=apt_packages)


def get_put_snapshot_sources_shell_command(
        snapshot_date: datetime.datetime, 
        version_code: str, 
        os_release_id: OSReleaseID,
        debian_backports: bool = False,
        keep_apt_cache: bool = False,
        ) -> str:
    """
    Taken from https://github.com/reproducible-containers/repro-sources-list.sh/blob/master/repro-sources-list.sh

    In order to use snapshot archives, the snapshot locations need to be put into the sources list of apt.
    This function generates the shell commands to set up the sources.list etc. accordingly.

    """
    snapshot = snapshot_date.strftime("%Y%m%dT%H%M%SZ")

    run_command = str

    keep_apt_cache_command = [
    """rm -f /etc/apt/apt.conf.d/docker-clean""",
	"""echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' >/etc/apt/apt.conf.d/keep-cache"""
    ]

    match os_release_id:

        case OSReleaseID.DEBIAN:

            snapshot_archive_base = "http://snapshot.debian.org/archive/"

            commands: list[str] = []
            commands.append("""if [ -e /etc/apt/sources.list.d/debian.sources ]; then rm -f /etc/apt/sources.list.d/debian.sources; fi;""")
            commands.append(f"""echo "deb [check-valid-until=no] {snapshot_archive_base}debian/{snapshot} {version_code} main" >/etc/apt/sources.list;""")
            commands.append(f"""echo "deb [check-valid-until=no] {snapshot_archive_base}debian-security/{snapshot} {version_code}-security main" >>/etc/apt/sources.list;""")
            commands.append(f"""echo "deb [check-valid-until=no] {snapshot_archive_base}debian/{snapshot} {version_code}-updates main" >>/etc/apt/sources.list;""")
            if debian_backports:
                commands.append(f"""echo "deb [check-valid-until=no] {snapshot_archive_base}debian/{snapshot} {version_code}-backports main" >>/etc/apt/sources.list;""")

            if keep_apt_cache:
                commands.extend(keep_apt_cache_command)

            run_command = "\\\n    ".join(commands)

            #TODO Debian >= 13 has new format
            
            
        case OSReleaseID.UBUNTU:

            snapshot_archive_base = "http://snapshot.ubuntu.com/"

            commands: list[str] = []

            commands.append("""if [ -e /etc/apt/sources.list.d/ubuntu.sources ]; then rm -f /etc/apt/sources.list.d/ubuntu.sources; fi;""")
            commands.append(f"""echo "deb [check-valid-until=no] {snapshot_archive_base}ubuntu/{snapshot} {version_code} main restricted" >/etc/apt/sources.list;""")
            commands.append(f"""echo "deb [check-valid-until=no] {snapshot_archive_base}ubuntu/{snapshot} {version_code}-updates main restricted" >>/etc/apt/sources.list;""")
            commands.append(f"""echo "deb [check-valid-until=no] {snapshot_archive_base}ubuntu/{snapshot} {version_code} universe" >>/etc/apt/sources.list;""")
            commands.append(f"""echo "deb [check-valid-until=no] {snapshot_archive_base}ubuntu/{snapshot} {version_code}-updates universe" >>/etc/apt/sources.list;""")
            commands.append(f"""echo "deb [check-valid-until=no] {snapshot_archive_base}ubuntu/{snapshot} {version_code} multiverse" >>/etc/apt/sources.list;""")
            commands.append(f"""echo "deb [check-valid-until=no] {snapshot_archive_base}ubuntu/{snapshot} {version_code}-updates multiverse" >>/etc/apt/sources.list;""")
            commands.append(f"""echo "deb [check-valid-until=no] {snapshot_archive_base}ubuntu/{snapshot} {version_code}-backports main restricted universe multiverse" >>/etc/apt/sources.list;""")
            commands.append(f"""echo "deb [check-valid-until=no] {snapshot_archive_base}ubuntu/{snapshot} {version_code}-security main restricted" >>/etc/apt/sources.list;""")
            commands.append(f"""echo "deb [check-valid-until=no] {snapshot_archive_base}ubuntu/{snapshot} {version_code}-security universe" >>/etc/apt/sources.list;""")
            commands.append(f"""echo "deb [check-valid-until=no] {snapshot_archive_base}ubuntu/{snapshot} {version_code}-security multiverse" >>/etc/apt/sources.list;""")

            if keep_apt_cache:
                commands.extend(keep_apt_cache_command)

            # http://snapshot.ubuntu.com is redirected to https, so we have to install ca-certificates
            commands.append("""export DEBIAN_FRONTEND=noninteractive;""")
            commands.append("""apt-get -o Acquire::https::Verify-Peer=false update >&2;""")
            commands.append("""apt-get -o Acquire::https::Verify-Peer=false install -y ca-certificates >&2;""")

            run_command = "\\\n    ".join(commands)
            #TODO Ubuntu >= 24.04 has new format
            
        case _:
            raise ValueError(f"The OS does not use apt: {os_release_id}")
    
    return run_command
