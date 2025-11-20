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
Client (10.0.1.10-12) -> Classification VNF (10.0.1.20) -> Policing VNF (10.0.2.21) -> Monitoring VNF (10.0.3.22) -> Server (10.0.4.100)


## Docker Environment 

All VNFs and endpoints are deployed using Docker Compose with multiple bridge networks to enforce traffic through the VNF chain.

### Network Configuration:
- **network_a** (10.0.1.0/24): Clients + Classification VNF
- **network_b** (10.0.2.0/24): Classification + Policing VNF  
- **network_c** (10.0.3.0/24): Policing + Monitoring VNF
- **network_d** (10.0.4.0/24): Monitoring VNF + Server

### Traffic Classification Rules:
| Traffic Type | Port | Protocol | DSCP Value | Class |
|--------------|------|----------|------------|-------|
| VoIP | 5004 | UDP | EF (46) | Expedited Forwarding |
| Video | 8080 | TCP | AF41 (34) | Assured Forwarding 4 |
| Data | 5001 | TCP | BE (0) | Best Effort |

## Quick Start

```bash
# Start VNF chain
docker-compose up -d

# Run scripts to test VNFs
.\scripts\test_vnfs.ps1 -Duration 30

# Monitor VNF logs
docker logs vnf_classification -f
docker logs vnf_policing -f  
docker logs vnf_monitoring -f

# Manual Testing
## Stop any existing servers
docker exec server pkill iperf3

## Start servers
docker exec -d server iperf3 -s -p 5001        # Data (TCP)
docker exec -d server iperf3 -s -p 5004 -u     # VoIP (UDP)
docker exec -d server iperf3 -s -p 8080        # Video (TCP)

## Generate traaffic

### VoIP Traffic (UDP, low latency):
docker exec client_voip iperf3 -c 10.0.0.100 -u -p 5004 -b 1M -l 160 -t 30

### VoIP Traffic (UDP, low latency):
docker exec client_video iperf3 -c 10.0.0.100 -p 8080 -b 10M -t 30

### Data Traffic (TCP, best effort):
docker exec client_data iperf3 -c 10.0.0.100 -p 5001 -t 30


## View VNF Statistics
docker logs vnf_classification --tail 5
docker logs vnf_policing --tail 50
docker logs vnf_monitoring --tail 50
