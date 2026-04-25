FROM docker.io/nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04

# Install Python and git (git is needed by pip to fetch mcp-knowledge-base
# from GitHub via the PEP 508 direct-reference URL in requirements.txt)
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/mcp-knowledge

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

# Copy application code
COPY mcp-service.py .
COPY ingest/ ingest/

# Knowledge volume mount point
RUN mkdir -p /opt/knowledge

EXPOSE 5184

CMD ["python3", "mcp-service.py"]
