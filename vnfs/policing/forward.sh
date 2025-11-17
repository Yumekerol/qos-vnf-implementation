#!/bin/bash
echo "=========================================="
echo "Configuring network for $VNF_NAME"
echo "=========================================="

# Verificar se estamos em container privilegiado
if [ -w /proc/sys/net/ipv4/ip_forward ]; then
    # Enable IP forwarding
    sysctl -w net.ipv4.ip_forward=1
    sysctl -w net.ipv4.conf.all.forwarding=1
    sysctl -w net.ipv4.conf.default.forwarding=1

    # Disable reverse path filtering
    sysctl -w net.ipv4.conf.all.rp_filter=0
    sysctl -w net.ipv4.conf.default.rp_filter=0
    sysctl -w net.ipv4.conf.eth0.rp_filter=0

    # Enable proxy ARP
    sysctl -w net.ipv4.conf.all.proxy_arp=1

    # Disable ICMP redirects
    sysctl -w net.ipv4.conf.all.send_redirects=0
    sysctl -w net.ipv4.conf.eth0.send_redirects=0
    echo "Network parameters configured!"
else
    echo "Running without sysctl permissions - using existing configuration"
fi

# Add route to next VNF
if [ -n "$NEXT_HOP" ]; then
    echo "Setting up route to next hop: $NEXT_HOP"
    ip route del default 2>/dev/null || true
    ip route add default via $NEXT_HOP
    echo "Route configured!"
else
    echo "WARNING: NEXT_HOP not defined!"
fi

echo ""
echo "Current routing table:"
ip route
echo ""
echo "Network interfaces:"
ip addr show eth0
echo ""
echo "IP forwarding status:"
cat /proc/sys/net/ipv4/ip_forward
echo "=========================================="