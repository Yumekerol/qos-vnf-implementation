FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    iperf3 \
    iproute2 \
    iputils-ping \
    tcpdump \
    netcat \
    curl \
    wget \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /logs /scripts

WORKDIR /scripts

CMD ["sleep", "infinity"]