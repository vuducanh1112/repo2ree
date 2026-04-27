FROM debian:bookworm-slim

############### INSTALL NIX ###############

# Install necessary dependencies for the Nix installer (+ direnv for development convenience)
RUN apt-get update && apt-get install -y \
    curl \
    xz-utils \
    sudo \
    ca-certificates \
    direnv \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user (Nix requires a home directory and non-root is best practice)
ENV USER=nixuser
RUN useradd -m -s /bin/bash $USER && \
    echo "$USER ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers
USER $USER

# Install Nix in single-user mode
# --no-daemon is used because Docker containers lack systemd
RUN curl -L https://nixos.org/nix/install | sh -s -- --no-daemon

# Set up the environment
ENV PATH="/home/$USER/.nix-profile/bin:$PATH"

# Verify installation
RUN nix-env --version

##############################################

WORKDIR /repo2ree
COPY flake.nix flake.lock ./

# Enable experimental features (nix-command and flakes)
RUN mkdir -p /home/$USER/.config/nix && \
    echo "experimental-features = nix-command flakes" >> /home/$USER/.config/nix/nix.conf

# Pre-build the dev shell
RUN nix develop --command true

# Set up direnv for the user (optional, but convenient for development)
RUN echo 'eval "$(direnv hook bash)"' >> /home/$USER/.bashrc

# Set up direnv
COPY .envrc ./
RUN echo 'eval "$(direnv hook bash)"' >> /home/$USER/.bashrc && \
    direnv allow .

USER root
COPY docker/dev/dev-entrypoint.sh /usr/local/bin/dev-entrypoint.sh
RUN chmod +x /usr/local/bin/dev-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/dev-entrypoint.sh"]
CMD ["bash"]
