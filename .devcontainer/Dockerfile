FROM python:3.13-slim

RUN apt-get update && apt-get install -y \
    vim-tiny \
    git \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

WORKDIR /workspace

CMD ["/bin/bash"]
