FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    iperf3 \
    iproute2 \
    iputils-ping \
    tcpdump \
    netcat \
    nginx \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /logs

EXPOSE 5001 5004/udp 8080

WORKDIR /root

CMD ["sleep", "infinity"]