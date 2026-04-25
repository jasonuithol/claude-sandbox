FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y git curl zip python3 python3-pip python3-venv && rm -rf /var/lib/apt/lists/*
RUN useradd -m -s /bin/bash -u 1000 claude
USER claude
RUN curl -fsSL https://claude.ai/install.sh | bash
ENV PATH="/home/claude/.local/bin:$PATH"
WORKDIR /workspace
CMD ["/bin/bash"]
