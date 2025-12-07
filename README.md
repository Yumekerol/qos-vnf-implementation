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

Client (10.0.0.10-12) -> Classification (10.0.0.20) -> Policing (10.0.0.21) -> Monitoring (10.0.0.22) -> Server (10.0.0.100)

## Docker Environment 

All VNFs and endpoints are deployed using Docker Compose with multiple bridge networks to enforce traffic through the VNF chain.

### Network Topology:
- Single bridge network: `qos_net` (10.0.0.0/24)
- **Service chaining**: Traffic flows through VNFs sequentially
- **Packet interception**: NetfilterQueue (NFQUEUE) captures packets at each VNF
- **Routing**: Static routes force traffic through the VNF chain

### Traffic Classification Rules:
| Traffic Type | Port | Protocol | DSCP Value | Class |
|--------------|------|----------|------------|-------|
| VoIP         | 5004 | UDP      | EF (46)    | Expedited Forwarding |
| Video        | 8080 | TCP      | AF41 (34)  | Assured Forwarding 4 |
| Data         | 5001 | TCP      | BE (0)     | Best Effort |

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.x
- Required Python libraries (`pandas`, `matplotlib`, `seaborn`)

### 1. Clone the repository
```bash
git clone https://github.com/Yumekerol/qos-vnf-implementation.git 
cd qos-vnf-implementation
```

### 2. Build and start the VNFs
```bash
docker-compose build
docker-compose up -d
docker-compose ps
```

## Running Tests

The project includes several automated scripts to test different scenarios and validate the QoS implementation.

### 1. Optimization Tests (Token Bucket Tuning)
Tests different token bucket configurations to find optimal parameters.
```bash
python scripts/optimize_test.py
```

### 2. Comprehensive Scenario Comparison
Compares multiple scenarios (Congested vs. Uncongested network states... etc.) to evaluate VNF performance under load.

```bash
python scripts/compare_comprehensive_scenarios.py
```
To analyze the results:
```bash
python scripts/analyse_results.py ./test_results/comprehensive_<numbers of the results>
```

### 3. Policing Verification
Compares network performance **with** vs. **without** the Policing VNF to measure its impact and overhead.
```bash
python scripts/compare_without_police.py
```
To visualize the comparison:

```bash
python scripts/analyse_compare.py ./test_results/compare_without_police_<numbers of the results>
```