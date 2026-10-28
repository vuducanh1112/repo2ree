# The dev container: Debian with Nix, both pinned by digest. Debian is the base so that
# VS Code's server runs in it (it needs glibc's loader at /lib64 and libstdc++); Nix,
# with its store, settings, and CA bundle, comes from the official image, so there is
# no installer script and no apt. flake.lock fixes everything installed on top. Bump
# the digests deliberately:
#   docker buildx imagetools inspect nixos/nix:latest
#   docker buildx imagetools inspect debian:bookworm-slim
FROM nixos/nix:latest@sha256:f159a58f390677f41e8e900a74b6e2f9c7f27b364122ae6acf7a652ce6c551c0 AS nix

FROM debian:bookworm-slim@sha256:99c0b25c46d0214d5a2091092e7908907dcaecd6a962cde0ac700acee222b6f3

# Nix as the official image has it: the store with its database and profiles, its
# settings (build users, no sandbox in a container), and the users it builds as. /nix
# belongs to root: the entrypoint starts the Nix daemon and the user builds through it,
# so /nix is never chowned (which would copy the whole store into a new layer).
COPY --from=nix /nix /nix
COPY --from=nix /etc/nix /etc/nix
RUN ln -s /nix/var/nix/profiles/default /root/.nix-profile \
    && echo 'experimental-features = nix-command flakes' >> /etc/nix/nix.conf \
    && groupadd -g 30000 nixbld \
    && for i in $(seq 1 32); do \
        useradd -M -N -u $((30000 + i)) -g nixbld -G nixbld -s /usr/sbin/nologin "nixbld$i"; \
    done
ENV PATH=/root/.nix-profile/bin:/nix/var/nix/profiles/default/bin:/nix/var/nix/profiles/default/sbin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    NIX_SSL_CERT_FILE=/nix/var/nix/profiles/default/etc/ssl/certs/ca-bundle.crt \
    SSL_CERT_FILE=/nix/var/nix/profiles/default/etc/ssl/certs/ca-bundle.crt \
    GIT_SSL_CAINFO=/nix/var/nix/profiles/default/etc/ssl/certs/ca-bundle.crt

RUN useradd -m -u 1000 -s /bin/bash nixuser \
    && echo 'eval "$(direnv hook bash)"' >> /home/nixuser/.bashrc

# The entrypoint's tools and a warm dev shell, both GC-rooted. Root builds without
# a daemon here; at runtime the user's builds find these paths already in the store.
# Built from a directory of its own: the checkout is mounted at /repo2ree, and a
# volume mounted where the image has files starts with root's copy of them.
WORKDIR /opt/repo2ree-devshell
COPY flake.nix flake.lock ./
COPY nix ./nix
RUN nix build .#devcontainer --out-link /opt/devcontainer \
    && nix develop --profile /nix/var/nix/profiles/repo2ree-devshell --command true
ENV PATH="/opt/devcontainer/bin:${PATH}"
# Debian's /etc/profile sets PATH anew for every login shell, which runs use; the
# image's PATH comes back after it, from profile.d.
RUN echo "export PATH=\"$PATH\"" > /etc/profile.d/dev-path.sh

# direnv trusts the mounted repo as a whole, so its .envrc loads without `direnv allow`,
# edits included. After the dev shell, so changing it rebuilds nothing heavy.
RUN mkdir -p /home/nixuser/.config/direnv \
    && printf '[whitelist]\nprefix = ["/repo2ree"]\n' > /home/nixuser/.config/direnv/direnv.toml \
    && chown -R nixuser: /home/nixuser/.config

COPY docker/dev/nix-entrypoint.sh /usr/local/bin/dev-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/dev-entrypoint.sh"]
CMD ["bash"]
