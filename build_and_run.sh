CLEAN=false
NO_BUILD=false
VALIDATE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --clean)
            CLEAN=true
            shift
            ;;
        --no-build)
            NO_BUILD=true
            shift
            ;;
        --validate)
            VALIDATE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo ""
echo "========================================="
echo " QoS VNF Project - Build & Deploy"
echo "========================================="
echo ""

if [ "$CLEAN" = true ]; then
    echo "Step 1: Cleaning up existing containers..."
    docker-compose down -v 2>/dev/null
    echo "   ✓ Cleanup complete"
    echo ""
    sleep 2
fi

if [ "$NO_BUILD" = false ]; then
    echo "Step 2: Building Docker containers..."
    docker-compose build --no-cache

    if [ $? -ne 0 ]; then
        echo "   ✗ Build failed!"
        exit 1
    fi

    echo "   ✓ Build complete"
    echo ""
fi

echo "Step 3: Starting containers..."
docker-compose up -d

if [ $? -ne 0 ]; then
    echo "   ✗ Failed to start containers!"
    exit 1
fi

echo "   ✓ Containers started"
echo ""

echo "Step 4: Waiting for initialization..."
for i in {1..15}; do
    echo -n "."
    sleep 1
done
echo ""
echo "   ✓ Initialization complete"
echo ""

echo "Step 5: Configuring routing..."
./setup_routing.sh
if [ "$VALIDATE" = true ]; then
    echo ""
    echo "Step 6: Validating chain..."
    ./scripts/validate_chain.sh
fi

echo ""
echo "========================================="
echo " Deployment Complete!"
echo "========================================="
echo ""

echo "Container Status:"
docker-compose ps

echo ""
echo "Next Steps:"
echo "  1. Validate chain:  ./scripts/validate_chain.sh"
echo "  2. Quick test:      ./scripts/quick_test.sh"
echo "  3. Full test:       ./scripts/traffic_test.sh -Duration 30"
echo ""
echo "View logs:"
echo "  docker logs vnf_classification -f"
echo "  docker logs vnf_policing -f"
echo "  docker logs vnf_monitoring -f"
echo ""