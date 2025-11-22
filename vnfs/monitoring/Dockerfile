FROM python:3.9-slim

# Install ALL system dependencies FIRST (including build tools)
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    libnetfilter-queue-dev \
    iproute2 \
    iputils-ping \
    tcpdump \
    iptables \
    net-tools \
    procps \
    traceroute \
    inetutils-traceroute \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Enforce iptables-legacy
RUN update-alternatives --set iptables /usr/sbin/iptables-legacy || true
RUN update-alternatives --set ip6tables /usr/sbin/ip6tables-legacy || true

# NOW install Python packages (after build tools are ready)
RUN pip install --no-cache-dir scapy NetfilterQueue

RUN mkdir -p /logs /metrics /app

COPY monitor.py /app/
COPY forward.sh /app/
RUN dos2unix /app/forward.sh && chmod +x /app/forward.sh

WORKDIR /app

CMD ["/bin/bash", "-c", "/app/forward.sh && python3 -u /app/monitor.py"]