FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    iproute2 \
    iputils-ping \
    tcpdump \
    iptables \
    net-tools \
    procps \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir scapy

RUN mkdir -p /logs /app

COPY classify.py /app/
COPY forward.sh /app/
RUN chmod +x /app/classify.py /app/forward.sh

WORKDIR /app

CMD ["/bin/bash", "-c", "/app/forward.sh && python3 -u /app/classify.py"]