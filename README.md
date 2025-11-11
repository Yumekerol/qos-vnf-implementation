# QoS VNF Implementation

University of Minho - Internet Quality of Service Course  
TP3: QoS Implementation using Virtual Network Functions

## Overview
Implementation of Quality of Service mechanisms using Virtual Network Functions that inclues:

- classification
- policing
- monitoring
- scheduling
- control access

## Docker Environment
All VNFs and endpoints are deployed using Docker containers connected via a custom network (`qos_net`).

- Each container has a **static IP address**.
- Networking is handled through a **Docker bridge** or optionally **Open vSwitch (OVS)**.
- For realistic network emulation (latency, loss, bandwidth), the setup can integrate:
  - **Linux traffic control (tc)**
  - **Containernet** (Mininet with Docker support) - this will be our main option
