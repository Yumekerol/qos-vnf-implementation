FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    iptables \
    iproute2 \
    iputils-ping \
    tcpdump \
    net-tools \
    rsyslog \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /logs /app /etc/iptables

COPY firewall.sh /app/
RUN chmod +x /app/firewall.sh

WORKDIR /app

CMD ["/bin/bash", "/app/firewall.sh"]