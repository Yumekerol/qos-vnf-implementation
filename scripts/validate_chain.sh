echo "========================================="
echo " VNF Chain Validation Script"
echo "========================================="
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "1. Checking container status..."
echo "-----------------------------------"
for container in client_voip client_video client_data vnf_classification vnf_policing vnf_monitoring vnf_scheduling vnf_access_control server; do
    if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        echo -e "${GREEN}✓${NC} $container is running"
    else
        echo -e "${RED}✗${NC} $container is NOT running"
    fi
done

echo ""
echo "2. Checking IP forwarding on VNFs..."
echo "-----------------------------------"
for vnf in vnf_classification vnf_policing vnf_monitoring vnf_scheduling vnf_access_control; do
    forwarding=$(docker exec $vnf sysctl net.ipv4.ip_forward 2>/dev/null | awk '{print $3}')
    if [ "$forwarding" = "1" ]; then
        echo -e "${GREEN}✓${NC} $vnf: IP forwarding ENABLED"
    else
        echo -e "${RED}✗${NC} $vnf: IP forwarding DISABLED"
    fi
done

echo ""
echo "3. Checking routing tables..."
echo "-----------------------------------"
for vnf in vnf_classification vnf_policing vnf_monitoring vnf_scheduling vnf_access_control; do
    echo -e "${YELLOW}$vnf:${NC}"
    docker exec $vnf ip route 2>/dev/null | grep default || echo "  No default route"
done

echo ""
echo "4. Testing chain connectivity (ping)..."
echo "-----------------------------------"

echo "Client -> Classification VNF:"
if docker exec client_voip ping -c 2 -W 2 10.0.0.20 > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Reachable"
else
    echo -e "${RED}✗${NC} Unreachable"
fi

echo "Classification -> Policing VNF:"
if docker exec vnf_classification ping -c 2 -W 2 10.0.0.21 > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Reachable"
else
    echo -e "${RED}✗${NC} Unreachable"
fi

echo "Policing -> Monitoring VNF:"
if docker exec vnf_policing ping -c 2 -W 2 10.0.0.22 > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Reachable"
else
    echo -e "${RED}✗${NC} Unreachable"
fi

echo "Monitoring -> Scheduling VNF:"
if docker exec vnf_monitoring ping -c 2 -W 2 10.0.0.23 > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Reachable"
else
    echo -e "${RED}✗${NC} Unreachable"
fi

echo "Scheduling -> Access Control VNF:"
if docker exec vnf_scheduling ping -c 2 -W 2 10.0.0.24 > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Reachable"
else
    echo -e "${RED}✗${NC} Unreachable"
fi

echo "Access Control -> Server:"
if docker exec vnf_access_control ping -c 2 -W 2 10.0.0.100 > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Reachable"
else
    echo -e "${RED}✗${NC} Unreachable"
fi

echo ""
echo "5. End-to-end connectivity test..."
echo "-----------------------------------"
echo "Client VoIP -> Server (through chain):"
if docker exec client_voip ping -c 3 -W 3 10.0.0.100 > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} SUCCESS - Client can reach server through VNF chain"
else
    echo -e "${RED}✗${NC} FAILED - Client cannot reach server"
fi

echo ""
echo "6. Traceroute from client to server..."
echo "-----------------------------------"
docker exec client_voip traceroute -n -m 10 -w 2 10.0.0.100 2>/dev/null || echo "Traceroute not available"

echo ""
echo "7. Checking VNF processes..."
echo "-----------------------------------"
echo "Classification VNF:"
docker exec vnf_classification ps aux | grep -E "(python|classify)" | grep -v grep || echo "  No Python process found"

echo "Policing VNF:"
docker exec vnf_policing ps aux | grep -E "(python|police)" | grep -v grep || echo "  No Python process found"

echo "Monitoring VNF:"
docker exec vnf_monitoring ps aux | grep -E "(python|monitor)" | grep -v grep || echo "  No Python process found"

echo ""
echo "========================================="
echo " Validation Complete"
echo "========================================="