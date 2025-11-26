#!/bin/bash
echo "=========================================="
echo "Configuring network for $VNF_NAME"
echo "=========================================="

if [ -w /proc/sys/net/ipv4/ip_forward ]; then
    sysctl -w net.ipv4.ip_forward=1
    sysctl -w net.ipv4.conf.all.forwarding=1
    sysctl -w net.ipv4.conf.default.forwarding=1

    sysctl -w net.ipv4.conf.all.rp_filter=0
    sysctl -w net.ipv4.conf.default.rp_filter=0
    sysctl -w net.ipv4.conf.eth0.rp_filter=0

    sysctl -w net.ipv4.conf.all.proxy_arp=1

    sysctl -w net.ipv4.conf.all.send_redirects=0
    sysctl -w net.ipv4.conf.eth0.send_redirects=0

    echo "✓ Network parameters configured!"
else
    echo "⚠ Running without sysctl permissions - using existing configuration"
fi

if [ -n "$NEXT_HOP" ]; then
    echo "Setting up route to next hop: $NEXT_HOP"
    ip route del default 2>/dev/null || true
    ip route add default via $NEXT_HOP

    if [ -n "$DEST_IP" ]; then
        if [ "$DEST_IP" == "$NEXT_HOP" ]; then
            echo "Next hop is destination. Using direct routing."
        else
            echo "Adding specific route to destination $DEST_IP via $NEXT_HOP"
            ip route add $DEST_IP/32 via $NEXT_HOP
        fi
    fi

    echo "✓ Route configured!"
else
    echo "⚠ WARNING: NEXT_HOP not defined!"
fi

echo "Enabling Masquerade (SNAT)..."
iptables-legacy -t nat -A POSTROUTING -o eth0 -j MASQUERADE

echo ""
echo "Setting up iptables NFQUEUE (BIDIRECTIONAL)..."

iptables-legacy -F FORWARD

if iptables-legacy -A FORWARD -j NFQUEUE --queue-num 0 2>/dev/null; then
    echo "✓ iptables-legacy: NFQUEUE configured for ALL traffic (bidirectional)"
elif iptables -A FORWARD -j NFQUEUE --queue-num 0 2>/dev/null; then
    echo "✓ iptables: NFQUEUE configured for ALL traffic (bidirectional)"
else
    echo "✗ ERROR: Failed to configure iptables NFQUEUE!"
    echo "Trying fallback QUEUE target..."
    if iptables-legacy -A FORWARD -j QUEUE 2>/dev/null; then
        echo "✓ iptables-legacy: QUEUE configured (fallback)"
    elif iptables -A FORWARD -j QUEUE 2>/dev/null; then
        echo "✓ iptables: QUEUE configured (fallback)"
    else
        echo "✗✗ CRITICAL: Failed all iptables configurations!"
    fi
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
echo ""
echo "iptables FORWARD rules:"
iptables-legacy -L FORWARD -n -v
echo "=========================================="