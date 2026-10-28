# The dev container on a Nix base image, pinned by digest: the digest fixes Nix and
# the base files, and flake.lock fixes everything installed on top. No apt, no
# installer script. Bump the digest deliberately:
#   docker buildx imagetools inspect nixos/nix:latest
FROM nixos/nix:latest@sha256:f159a58f390677f41e8e900a74b6e2f9c7f27b364122ae6acf7a652ce6c551c0

# The base's /nix belongs to root and its builders. The entrypoint starts the Nix
# daemon as root and the user builds through it, so /nix is never chowned (which
# would copy the whole store into a new layer).
RUN echo 'experimental-features = nix-command flakes' >> /etc/nix/nix.conf

# The user, written directly: the base has no useradd, and two lines need none.
RUN echo 'nixuser:x:1000:1000:nixuser:/home/nixuser:/bin/bash' >> /etc/passwd \
    && echo 'nixuser:x:1000:' >> /etc/group \
    && mkdir -p /home/nixuser \
    && echo 'eval "$(direnv hook bash)"' > /home/nixuser/.bashrc \
    && chown -R 1000:1000 /home/nixuser

# The entrypoint's tools and a warm dev shell, both GC-rooted. Root builds without
# a daemon here; at runtime the user's builds find these paths already in the store.
WORKDIR /repo2ree
COPY flake.nix flake.lock ./
COPY nix ./nix
RUN nix build .#devcontainer --out-link /opt/devcontainer \
    && nix develop --profile /nix/var/nix/profiles/repo2ree-devshell --command true
ENV PATH="/opt/devcontainer/bin:${PATH}"

# direnv trusts the mounted repo as a whole, so its .envrc loads without `direnv allow`,
# edits included. After the dev shell, so changing it rebuilds nothing heavy.
RUN mkdir -p /home/nixuser/.config/direnv \
    && printf '[whitelist]\nprefix = ["/repo2ree"]\n' > /home/nixuser/.config/direnv/direnv.toml \
    && chown -R 1000:1000 /home/nixuser/.config

COPY docker/dev/nix-entrypoint.sh /usr/local/bin/dev-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/dev-entrypoint.sh"]
CMD ["bash"]
