FROM python:3.11-slim

# Install required packages
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    gnupg \
    apt-transport-https

# Download kubectl
RUN curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"

# Make it executable and move to path
RUN chmod +x kubectl && mv kubectl /usr/local/bin/

# Clean up
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install websockets requests kubernetes rlp multihash base58 eth-enr eth-keys

COPY init_container.py /init_container.py
