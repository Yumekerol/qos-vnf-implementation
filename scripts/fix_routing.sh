echo "=========================================="
echo "Fixing VNF Chain Routing"
echo "=========================================="

echo ""
echo "1. Enabling IP forwarding on VNFs..."
for vnf in vnf_classification vnf_policing vnf_monitoring vnf_scheduling vnf_access_control; do
    echo "   Configuring $vnf..."
    docker exec $vnf sysctl -w net.ipv4.ip_forward=1 2>/dev/null
    docker exec $vnf sysctl -w net.ipv4.conf.all.rp_filter=0 2>/dev/null
    docker exec $vnf sysctl -w net.ipv4.conf.default.rp_filter=0 2>/dev/null
    docker exec $vnf sysctl -w net.ipv4.conf.eth0.rp_filter=0 2>/dev/null
done

# Setup NAT/forwarding on each VNF
echo ""
echo "2. Setting up NAT on VNFs..."

# Classification VNF
docker exec vnf_classification iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
docker exec vnf_classification iptables -A FORWARD -j ACCEPT
echo "   ✓ vnf_classification"

# Policing VNF
docker exec vnf_policing iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
docker exec vnf_policing iptables -A FORWARD -j ACCEPT
echo "   ✓ vnf_policing"

# Monitoring VNF
docker exec vnf_monitoring iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
docker exec vnf_monitoring iptables -A FORWARD -j ACCEPT
echo "   ✓ vnf_monitoring"

# Scheduling VNF
docker exec vnf_scheduling iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
docker exec vnf_scheduling iptables -A FORWARD -j ACCEPT
echo "   ✓ vnf_scheduling"

echo "   ✓ vnf_access_control (already configured)"

echo ""
echo "3. Configuring client routing..."
for client in client_voip client_video client_data; do
    echo "   Configuring $client..."
    docker exec $client ip route del default 2>/dev/null || true
    docker exec $client ip route add default via 10.0.0.20
done

echo ""
echo "4. Setting up static routes on VNFs..."

# Classification -> Policing
docker exec vnf_classification ip route del default 2>/dev/null || true
docker exec vnf_classification ip route add default via 10.0.0.21

# Policing -> Monitoring
docker exec vnf_policing ip route del default 2>/dev/null || true
docker exec vnf_policing ip route add default via 10.0.0.22

# Monitoring -> Scheduling
docker exec vnf_monitoring ip route del default 2>/dev/null || true
docker exec vnf_monitoring ip route add default via 10.0.0.23

# Scheduling -> Access Control
docker exec vnf_scheduling ip route del default 2>/dev/null || true
docker exec vnf_scheduling ip route add default via 10.0.0.24

# Access Control -> Server
docker exec vnf_access_control ip route del default 2>/dev/null || true
docker exec vnf_access_control ip route add default via 10.0.0.100

echo ""
echo "=========================================="
echo "Routing configuration complete!"
echo "=========================================="

echo ""
echo "Testing connectivity..."
if docker exec client_voip ping -c 2 -W 2 10.0.0.100 > /dev/null 2>&1; then
    echo "✓ Client can reach server through VNF chain"
else
    echo "✗ Client cannot reach server - check logs"
fi

echo ""
echo "Traceroute from client to server:"
docker exec client_voip traceroute -n -m 10 -w 1 10.0.0.100 2>/dev/null || echo "Traceroute not available"