FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y git curl zip && rm -rf /var/lib/apt/lists/*
RUN useradd -m -s /bin/bash -u 1000 jason
USER jason
RUN curl -fsSL https://claude.ai/install.sh | bash
ENV PATH="/home/jason/.local/bin:$PATH"
WORKDIR /workspace
CMD ["/bin/bash"]
