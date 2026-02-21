FROM debian:bookworm-slim

############### INSTALL NIX ###############

# 1. Install necessary dependencies for the Nix installer
RUN apt-get update && apt-get install -y \
    curl \
    xz-utils \
    sudo \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 2. Create a non-root user (Nix requires a home directory and non-root is best practice)
ENV USER=nixuser
RUN useradd -m -s /bin/bash $USER && \
    echo "$USER ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers
USER $USER

# 3. Install Nix in single-user mode
# --no-daemon is used because Docker containers lack systemd
RUN curl -L https://nixos.org/nix/install | sh -s -- --no-daemon

# 4. Set up the environment
ENV PATH="/home/$USER/.nix-profile/bin:$PATH"
ENV NIX_PATH="nixpkgs=channel:nixpkgs-unstable"

# Verify installation
RUN nix-env --version

##############################################

WORKDIR /repo2ree
COPY flake.nix flake.lock* ./

# 3.5 Enable experimental features (nix-command and flakes)
RUN mkdir -p /home/$USER/.config/nix && \
    echo "experimental-features = nix-command flakes" >> /home/$USER/.config/nix/nix.conf && \
    sudo mkdir -p /etc/nix && \
    echo "experimental-features = nix-command flakes" | sudo tee -a /etc/nix/nix.conf

RUN nix develop --build

CMD ["bash"]
