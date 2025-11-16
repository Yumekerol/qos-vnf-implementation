echo "=========================================="
echo "Starting Access Control VNF (Firewall)"
echo "=========================================="

echo "Enabling IP forwarding..."
sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv4.conf.all.forwarding=1
sysctl -w net.ipv4.conf.default.forwarding=1

sysctl -w net.ipv4.conf.all.rp_filter=0
sysctl -w net.ipv4.conf.default.rp_filter=0
sysctl -w net.ipv4.conf.eth0.rp_filter=0

# Enable proxy ARP
sysctl -w net.ipv4.conf.all.proxy_arp=1

sysctl -w net.ipv4.conf.all.send_redirects=0
sysctl -w net.ipv4.conf.eth0.send_redirects=0

echo "IP forwarding enabled!"

if [ -n "$NEXT_HOP" ]; then
    echo "Setting up route to server: $NEXT_HOP"
    ip route del default 2>/dev/null || true
    ip route add default via $NEXT_HOP
    echo "Route configured!"
fi

echo ""
echo "Configuring iptables rules..."

iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X

iptables -P INPUT ACCEPT
iptables -P FORWARD ACCEPT  # ACCEPT for forwarding
iptables -P OUTPUT ACCEPT

iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE

# Allow loopback
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# Allow established connections
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A FORWARD -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# Allow ICMP (ping)
iptables -A INPUT -p icmp -j ACCEPT
iptables -A FORWARD -p icmp -j ACCEPT

echo ""
echo "===== ALLOWED TRAFFIC ====="

# Allow VoIP traffic (UDP port 5004)
iptables -A FORWARD -p udp --dport 5004 -j ACCEPT
iptables -A INPUT -p udp --dport 5004 -j ACCEPT
echo "✓ Allowed: VoIP traffic on UDP port 5004"

# Allow Video traffic (TCP port 8080)
iptables -A FORWARD -p tcp --dport 8080 -j ACCEPT
iptables -A INPUT -p tcp --dport 8080 -j ACCEPT
echo "✓ Allowed: Video traffic on TCP port 8080"

# Allow Data traffic (TCP port 5001 - iperf3)
iptables -A FORWARD -p tcp --dport 5001 -j ACCEPT
iptables -A INPUT -p tcp --dport 5001 -j ACCEPT
echo "✓ Allowed: Data traffic on TCP port 5001"

iptables -A INPUT -p tcp --dport 22 -j ACCEPT
echo "✓ Allowed: SSH on TCP port 22"

echo ""
echo "===== BLOCKED TRAFFIC ====="

# iptables -A INPUT -s 192.168.100.100 -j DROP
# iptables -A FORWARD -s 192.168.100.100 -j DROP

# Block specific port range
iptables -A INPUT -p tcp --dport 23 -j DROP      # Telnet
iptables -A INPUT -p tcp --dport 445 -j DROP     # SMB
iptables -A INPUT -p tcp --dport 3389 -j DROP    # RDP
echo "✗ Blocked: Telnet (23), SMB (445), RDP (3389)"

echo ""
echo "===== LOGGING ====="

iptables -A INPUT -m limit --limit 5/min -j LOG --log-prefix "IPTABLES-INPUT-DROP: " --log-level 4
iptables -A FORWARD -m limit --limit 5/min -j LOG --log-prefix "IPTABLES-FORWARD-DROP: " --log-level 4

# iptables -A INPUT -j DROP
# iptables -A FORWARD -j DROP

echo ""
echo "=========================================="
echo "Firewall configuration complete!"
echo "=========================================="
echo ""
echo "Current iptables rules:"
iptables -L -n -v --line-numbers

echo ""
echo "NAT rules:"
iptables -t nat -L -n -v

echo ""
echo "Saving iptables rules..."
if command -v iptables-save > /dev/null; then
    mkdir -p /etc/iptables
    iptables-save > /etc/iptables/rules.v4 2>/dev/null || \
    iptables-save > /logs/iptables-rules.txt
    echo "✓ Rules saved!"
fi

echo ""
echo "=========================================="
echo "Access Control VNF ready!"
echo "=========================================="

exec > /logs/access_control.log 2>&1

echo ""
echo "Starting firewall monitoring..."
echo "Logging blocked packets and connection attempts..."

while true; do
    echo "============================================"
    date
    echo ""
    echo "Firewall Statistics:"
    iptables -L -n -v --line-numbers | head -30
    echo ""
    echo "NAT Statistics:"
    iptables -t nat -L -n -v | head -20
    echo ""
    echo "Connection Tracking:"
    cat /proc/net/nf_conntrack 2>/dev/null | wc -l
    echo " active connections"
    echo ""
    sleep 10
done