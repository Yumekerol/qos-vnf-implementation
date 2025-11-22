# QoS VNF Implementation

**University of Minho - Internet Quality of Service Course**  
**TP3: QoS Implementation using Virtual Network Functions**

## Overview

Implementation of Quality of Service mechanisms using Virtual Network Functions including:

**Implemented VNFs:**
- **Classification VNF** - Traffic classification by port and DSCP marking
- **Policing VNF** - Token bucket rate limiting 
- **Monitoring VNF** - Real-time traffic metrics collection

## Architecture
Client (10.0.0.10-12) -> Classification (10.0.0.20) -> ... -> Server (10.0.0.100)


## Docker Environment 

All VNFs and endpoints are deployed using Docker Compose with multiple bridge networks to enforce traffic through the VNF chain.

### Network Topology:
- Single bridge network: qos_net (10.0.0.0/24)
- Service chaining: Traffic flows through VNFs sequentially
- Packet interception: NetfilterQueue (NFQUEUE) captures packets at each VNF
- Routing: Static routes force traffic through the VNF chain

### Traffic Classification Rules:
| Traffic Type | Port | Protocol | DSCP Value | Class |
|--------------|------|----------|------------|-------|
| VoIP | 5004 | UDP | EF (46) | Expedited Forwarding |
| Video | 8080 | TCP | AF41 (34) | Assured Forwarding 4 |
| Data | 5001 | TCP | BE (0) | Best Effort |

# Quick Start
## Clone the repository
```bash
git clone https://github.com/Yumekerol/qos-vnf-implementation.git 
cd qos-vnf-implementation
```

# Build and start the VNFs
```bash
docker-compose build
docker-compose up -d
docker-compose ps
```

# Test the VNF chain
```bash
docker exec client_voip ping -c 5 10.0.0.100  


# Start the server iperf3
docker exec -d server iperf3 -s -p 5004 -u

# Generate VoIP traffic (Need to fix)
docker exec client_voip iperf3 -c 10.0.0.100 -p 5004 -u -b 200K -t 30 -l 160


# Start the server
docker exec -d server iperf3 -s -p 8080

# Generate video traffic
docker exec client_video iperf3 -c 10.0.0.100 -p 8080 -b 5M -t 30


# Start the server
docker exec -d server iperf3 -s -p 5001

# Generate data traffic
docker exec client_data iperf3 -c 10.0.0.100 -p 5001 -t 30
```
# Check VNF logs
```bash
# Classification VNF
docker-compose logs -f vnf_classification

# Policing VNF
docker-compose logs -f vnf_policing

# Monitoring VNF
docker-compose logs -f vnf_monitoring

```