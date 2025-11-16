FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    iproute2 \
    iputils-ping \
    tcpdump \
    iptables \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /logs /app

COPY schedule.sh /app/
RUN chmod +x /app/schedule.sh

WORKDIR /app

CMD ["/bin/bash", "/app/schedule.sh"]