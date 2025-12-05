import subprocess
import time
import json
import sys
from datetime import datetime
from pathlib import Path


def run_command(cmd, capture=False):
    try:
        if capture:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return result.stdout
        else:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0 and result.stderr:
                print(f"  Command warning: {result.stderr[:200]}")
            return None
    except Exception as e:
        print(f" Error: {e}")
        return None


def check_prerequisites():
    print("\n" + "=" * 60)
    print("✓  CHECKING PREREQUISITES")
    print("=" * 60)

    containers = ["client_voip", "client_video", "client_data", "server",
                  "vnf_classification", "vnf_policing", "vnf_monitoring"]

    print("\n1. Checking containers...")
    for container in containers:
        result = run_command(f"docker ps --filter name={container} --format '{{{{.Names}}}}'", capture=True)
        if container in result:
            print(f" {container} is running")
        else:
            print(f" {container} is NOT running!")
            return False

    print("\n2. Checking connectivity...")
    clients = ["client_voip", "client_video", "client_data"]
    for client in clients:
        result = run_command(f"docker exec {client} ping -c 1 -W 2 10.0.0.100", capture=True)
        if "1 received" in result or "1 packets received" in result:
            print(f" {client} can reach server")
        else:
            print(f" {client} CANNOT reach server!")
            print(f" Output: {result[:200]}")
            return False

    print("\n3. Checking iperf3...")
    for container in clients + ["server"]:
        result = run_command(f"docker exec {container} which iperf3", capture=True)
        if "/iperf3" in result or "iperf3" in result:
            print(f" iperf3 installed in {container}")
        else:
            print(f" iperf3 NOT found in {container}!")
            return False

    print("\n All prerequisites OK!")
    return True


def apply_network_condition(condition):
    vnfs = ["vnf_classification", "vnf_policing", "vnf_monitoring"]

    print(f"\n{'=' * 60}")
    print(f"APPLYING NETWORK CONDITION: {condition}")
    print(f"{'=' * 60}")

    print("Clearing previous conditions...")
    for vnf in vnfs:
        run_command(f"docker exec {vnf} tc qdisc del dev eth0 root 2>/dev/null")
    time.sleep(1)

    if condition == "baseline":
        print("Baseline: No network impairments")

    elif condition == "congested_50mbps":
        print("Applying: Bandwidth limit 50 Mbps...")
        for vnf in vnfs:
            run_command(f"docker exec {vnf} tc qdisc add dev eth0 root tbf rate 50mbit burst 32kbit latency 400ms")

    elif condition == "congested_25mbps":
        print("Applying: Bandwidth limit 25 Mbps...")
        for vnf in vnfs:
            run_command(f"docker exec {vnf} tc qdisc add dev eth0 root tbf rate 25mbit burst 32kbit latency 400ms")

    elif condition == "congested_10mbps":
        print("Applying: Severe bandwidth limit 10 Mbps...")
        for vnf in vnfs:
            run_command(f"docker exec {vnf} tc qdisc add dev eth0 root tbf rate 10mbit burst 32kbit latency 400ms")

    elif condition == "packet_loss_1pct":
        print("Applying: 1% packet loss...")
        for vnf in vnfs:
            run_command(f"docker exec {vnf} tc qdisc add dev eth0 root netem loss 1%")

    elif condition == "packet_loss_5pct":
        print("Applying: 5% packet loss...")
        for vnf in vnfs:
            run_command(f"docker exec {vnf} tc qdisc add dev eth0 root netem loss 5%")

    elif condition == "variable_delay":
        print("Applying: Variable delay (50ms ± 20ms)...")
        for vnf in vnfs:
            run_command(f"docker exec {vnf} tc qdisc add dev eth0 root netem delay 50ms 20ms distribution normal")

    elif condition == "high_delay":
        print("Applying: High delay (100ms)...")
        for vnf in vnfs:
            run_command(f"docker exec {vnf} tc qdisc add dev eth0 root netem delay 100ms")

    elif condition == "combined_stress":
        print("Applying: Combined stress (25Mbps + 2% loss + 30ms delay)...")
        for vnf in vnfs:
            run_command(
                f"docker exec {vnf} tc qdisc add dev eth0 root handle 1: tbf rate 25mbit burst 32kbit latency 400ms")
            run_command(f"docker exec {vnf} tc qdisc add dev eth0 parent 1:1 handle 10: netem loss 2% delay 30ms")

    elif condition == "extreme_stress":
        print("Applying: Extreme stress (10Mbps + 5% loss + 50ms delay)...")
        for vnf in vnfs:
            run_command(
                f"docker exec {vnf} tc qdisc add dev eth0 root handle 1: tbf rate 10mbit burst 32kbit latency 400ms")
            run_command(f"docker exec {vnf} tc qdisc add dev eth0 parent 1:1 handle 10: netem loss 5% delay 50ms")

    time.sleep(2)
    print("Network condition applied")


def run_test(scenario_name, results_dir, duration=30):
    """Run a single test scenario"""
    scenario_dir = results_dir / scenario_name
    scenario_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print(f"RUNNING TEST: {scenario_name}")
    print("=" * 60)

    print("Cleaning up old iperf3 processes...")
    containers_to_clean = ["server", "client_voip", "client_video", "client_data"]
    for container in containers_to_clean:
        run_command(f"docker exec {container} pkill -9 iperf3 2>/dev/null")
    time.sleep(3)

    print("\n📡 Starting iperf3 servers...")
    run_command("docker exec -d server iperf3 -s -p 5004 -1")  # VoIP (UDP)
    run_command("docker exec -d server iperf3 -s -p 8080 -1")  # Video (TCP)
    run_command("docker exec -d server iperf3 -s -p 5001 -1")  # Data (TCP)
    time.sleep(3)

    print("Verifying servers are listening...")
    result = run_command("docker exec server netstat -tuln", capture=True)
    if "5004" in result and "8080" in result and "5001" in result:
        print("All servers listening")
    else:
        print("Warning: Some servers may not be listening")

    print(f"\nStarting traffic in PRIORITY ORDER ({duration}s test)")
    print("=" * 60)

    print("VoIP (UDP 150Kbps) starting...")
    run_command(
        f'docker exec -d client_voip sh -c "iperf3 -c 10.0.0.100 -p 5004 -u -b 150K -t {duration} -l 160 -J > /tmp/voip.json 2>&1"')
    print("Waiting 5 seconds for VoIP flow to stabilize...")
    time.sleep(5)  
    print("VoIP flow stable")

    print("Video (TCP 3Mbps) starting...")
    run_command(
        f'docker exec -d client_video sh -c "iperf3 -c 10.0.0.100 -p 8080 -b 3M -t {duration} -J > /tmp/video.json 2>&1"')
    print("Waiting 3 seconds for Video flow...")
    time.sleep(3)
    print("Video flow active")

    print("Data (TCP 20Mbps) starting...")
    run_command(
        f'docker exec -d client_data sh -c "iperf3 -c 10.0.0.100 -p 5001 -b 20M -t {duration} -J > /tmp/data.json 2>&1"')
    print("Data started (competing for remaining bandwidth)")

    print("\n" + "=" * 60)
    print("All flows active - test running...")
    print("=" * 60)

    for i in range(1, duration + 1):
        print(f"\r Progress: {i:2d}/{duration} seconds", end='', flush=True)
        time.sleep(1)
    print()

    print("Waiting for tests to complete...")
    time.sleep(5)

    print("Collecting results...")
    files_to_collect = [
        ('client_voip', '/tmp/voip.json', 'voip.json'),
        ('client_video', '/tmp/video.json', 'video.json'),
        ('client_data', '/tmp/data.json', 'data.json'),
        ('vnf_classification', '/logs/classification.log', 'classification.log'),
        ('vnf_policing', '/logs/policing.log', 'policing.log'),
        ('vnf_monitoring', '/logs/monitoring.log', 'monitoring.log')
    ]

    for container, src, dst in files_to_collect:
        target = scenario_dir / dst
        result = run_command(f'docker cp {container}:{src} "{target.resolve()}"', capture=True)

        if target.exists() and target.stat().st_size > 0:
            print(f" {dst}: {target.stat().st_size} bytes")
        else:
            print(f" {dst}: EMPTY or FAILED")
            if dst.endswith('.json'):
                error_output = run_command(f'docker exec {container} cat {src} 2>&1', capture=True)
                if error_output and len(error_output) > 0:
                    print(f"Content: {error_output[:200]}")

    print(f"Test completed: {scenario_name}\n")


def main():
    if not check_prerequisites():
        print("\nPrerequisites check failed! Fix issues above before continuing.")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = Path(f"./test_results/comprehensive_{timestamp}")
    results_dir.mkdir(parents=True, exist_ok=True)

    scenarios = [
        ("scenario1_baseline", "baseline"),
        ("scenario2_congested_50mbps", "congested_50mbps"),
        ("scenario3_congested_25mbps", "congested_25mbps"),
        ("scenario4_congested_10mbps", "congested_10mbps"),
        ("scenario5_packet_loss_1pct", "packet_loss_1pct"),
        ("scenario6_packet_loss_5pct", "packet_loss_5pct"),
        ("scenario7_variable_delay", "variable_delay"),
        ("scenario8_high_delay", "high_delay"),
        ("scenario9_combined_stress", "combined_stress"),
        ("scenario10_extreme_stress", "extreme_stress"),
    ]

    print("\n" + "=" * 60)
    print("COMPREHENSIVE QoS TESTING SUITE")
    print("=" * 60)
    print(f"\nThis will run {len(scenarios)} test scenarios")
    print(f"Duration: 30 seconds per scenario")
    print(f"Total time: ~{len(scenarios) * 0.6:.0f} minutes")
    print(f"Results: {results_dir}")

    input("\nPress Enter to start comprehensive testing...")

    for i, (scenario_name, condition) in enumerate(scenarios, 1):
        print(f"\n\n{'#' * 60}")
        print(f"# SCENARIO {i}/{len(scenarios)}: {scenario_name}")
        print(f"{'#' * 60}")

        apply_network_condition(condition)
        run_test(scenario_name, results_dir)

        if i < len(scenarios):
            print(f"\nWaiting 5 seconds before next scenario...")
            time.sleep(5)

    print("\nResetting network conditions...")
    apply_network_condition("baseline")

    print("\n" + "=" * 60)
    print("TESTING COMPLETE!")
    print("=" * 60)
    print(f"\nResults saved in: {results_dir}")
    print("\nNext steps:")
    print(f"  1. Analyze results:")
    print(f"     python analyze_results.py {results_dir}")
    print(f"  2. Review VNF logs in each scenario directory")
    print(f"  3. Document findings in Phase 3 report")

    input("\n  Press Enter to exit...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        print("Resetting network conditions...")
        apply_network_condition("baseline")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)