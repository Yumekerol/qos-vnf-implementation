echo "========================================="
echo " Setting up VNF chain routing"
echo "========================================="
echo ""

echo "Waiting for containers to initialize..."
sleep 5

echo ""
echo "Configuring client routing..."

for client in client_voip client_video client_data; do
    echo "  Configuring $client..."
    docker exec $client sh -c "
        ip route del default 2>/dev/null || true;
        ip route add default via 10.0.0.20;
        echo 'nameserver 8.8.8.8' > /etc/resolv.conf
    " 2>/dev/null

    if [ $? -eq 0 ]; then
        echo "    ✓ Configured successfully"
    else
        echo "    ✗ Configuration failed"
    fi
done

echo ""
echo "Enabling forwarding on VNFs..."

for vnf in vnf_classification vnf_policing vnf_monitoring vnf_scheduling vnf_access_control; do
    echo "  Configuring $vnf..."
    docker exec $vnf sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1
    docker exec $vnf sysctl -w net.ipv4.conf.all.rp_filter=0 >/dev/null 2>&1

    if [ $? -eq 0 ]; then
        echo "    ✓ Forwarding enabled"
    else
        echo "    ✗ Failed to enable forwarding"
    fi
done

echo ""
echo "========================================="
echo " Setup complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Run validation: ./scripts/validate_chain.sh"
echo "  2. Run tests: ./scripts/test_traffic.ps1 -Duration 30"
echo ""