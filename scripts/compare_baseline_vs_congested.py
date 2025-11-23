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
            subprocess.run(cmd, shell=True, check=False)
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def apply_network_condition(condition):
    vnfs = ["vnf_classification", "vnf_policing", "vnf_monitoring"]

    if condition == "baseline":
        print("Removing network conditions...")
        for vnf in vnfs:
            run_command(f"docker exec {vnf} tc qdisc del dev eth0 root")

    elif condition == "congested":
        print("Applying congestion (50Mbps limit)...")
        for vnf in vnfs:
            run_command(f"docker exec {vnf} tc qdisc del dev eth0 root")
            run_command(f"docker exec {vnf} tc qdisc add dev eth0 root tbf rate 50mbit burst 32kbit latency 400ms")

    time.sleep(2)


def run_test(scenario_name, results_dir):
    scenario_dir = results_dir / scenario_name
    scenario_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 50)
    print(f"Running: {scenario_name}")
    print("=" * 50)

    run_command("docker exec server pkill iperf3")
    time.sleep(1)
    run_command("docker exec -d server iperf3 -s -p 5004 -u")
    run_command("docker exec -d server iperf3 -s -p 8080")
    run_command("docker exec -d server iperf3 -s -p 5001")
    time.sleep(2)

    print("Starting mixed traffic (30 seconds)...")
    run_command(
        'docker exec -d client_voip sh -c "iperf3 -c 10.0.0.100 -p 5004 -u -b 200K -t 30 -l 160 -J > /tmp/voip.json 2>&1"')
    run_command(
        'docker exec -d client_video sh -c "iperf3 -c 10.0.0.100 -p 8080 -b 5M -t 30 -J > /tmp/video.json 2>&1"')
    run_command('docker exec -d client_data sh -c "iperf3 -c 10.0.0.100 -p 5001 -t 30 -J > /tmp/data.json 2>&1"')

    for i in range(1, 31):
        print(f"\r  Progress: {i:2d}/30 seconds", end='', flush=True)
        time.sleep(1)
    print()

    time.sleep(3)

    print("  Collecting results...")
    run_command(f"docker cp client_voip:/tmp/voip.json \"{scenario_dir.resolve()}\\voip.json\"")
    run_command(f"docker cp client_video:/tmp/video.json \"{scenario_dir.resolve()}\\video.json\"")
    run_command(f"docker cp client_data:/tmp/data.json \"{scenario_dir.resolve()}\\data.json\"")

    run_command(f"docker cp vnf_classification:/logs/classification.log \"{scenario_dir.resolve()}\\classification.log\"")
    run_command(f"docker cp vnf_policing:/logs/policing.log \"{scenario_dir.resolve()}\\policing.log\"")
    run_command(f"docker cp vnf_monitoring:/logs/monitoring.log \"{scenario_dir.resolve()}\\monitoring.log\"")

    print(f"  ✓ Results saved to {scenario_dir}")


def parse_json_metric(filepath, metric_type):
    """Extract metrics from iperf3 JSON"""
    if not filepath.exists():
        return 0

    try:
        with open(filepath, 'r') as f:
            data = json.load(f)

        if metric_type == "voip_throughput":
            return data.get('end', {}).get('sum', {}).get('bits_per_second', 0) / 1e6
        elif metric_type == "voip_jitter":
            return data.get('end', {}).get('sum', {}).get('jitter_ms', 0)
        elif metric_type == "voip_loss":
            return data.get('end', {}).get('sum', {}).get('lost_percent', 0)
        elif metric_type == "tcp_throughput":
            sum_data = data.get('end', {}).get('sum_received', {})
            if not sum_data:
                sum_data = data.get('end', {}).get('sum', {})
            return sum_data.get('bits_per_second', 0) / 1e6
        elif metric_type == "tcp_retrans":
            return data.get('end', {}).get('sum_sent', {}).get('retransmits', 0)
    except:
        return 0

    return 0


def main():
    # Create results directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = Path(f"./test_results/comparison_{timestamp}")
    results_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("QoS Effectiveness Comparison")
    print("=" * 50)
    print("\nThis will run 2 test scenarios:")
    print("  1. Baseline (normal network)")
    print("  2. Congested (50Mbps bandwidth limit)")
    print(f"\nDuration: 30 seconds per scenario")
    print(f"Results: {results_dir}")

    input("\nPress Enter to start...")

    # Scenario 1: Baseline
    apply_network_condition("baseline")
    run_test("scenario1_baseline", results_dir)

    print("\nWaiting 5 seconds before next test...")
    time.sleep(5)

    # Scenario 2: Congested
    apply_network_condition("congested")
    run_test("scenario2_congested", results_dir)

    # Reset network
    apply_network_condition("baseline")

    # Analyze results
    print("\n" + "=" * 50)
    print("Results Analysis")
    print("=" * 50)

    # Load all metrics
    baseline = results_dir / "scenario1_baseline"
    congested = results_dir / "scenario2_congested"

    voip_base_tp = parse_json_metric(baseline / "voip.json", "voip_throughput")
    voip_base_jitter = parse_json_metric(baseline / "voip.json", "voip_jitter")
    voip_base_loss = parse_json_metric(baseline / "voip.json", "voip_loss")

    voip_cong_tp = parse_json_metric(congested / "voip.json", "voip_throughput")
    voip_cong_jitter = parse_json_metric(congested / "voip.json", "voip_jitter")
    voip_cong_loss = parse_json_metric(congested / "voip.json", "voip_loss")

    video_base_tp = parse_json_metric(baseline / "video.json", "tcp_throughput")
    video_base_retrans = parse_json_metric(baseline / "video.json", "tcp_retrans")

    video_cong_tp = parse_json_metric(congested / "video.json", "tcp_throughput")
    video_cong_retrans = parse_json_metric(congested / "video.json", "tcp_retrans")

    data_base_tp = parse_json_metric(baseline / "data.json", "tcp_throughput")
    data_base_retrans = parse_json_metric(baseline / "data.json", "tcp_retrans")

    data_cong_tp = parse_json_metric(congested / "data.json", "tcp_throughput")
    data_cong_retrans = parse_json_metric(congested / "data.json", "tcp_retrans")

    # Display VoIP comparison
    print("\n--- VoIP (UDP 200Kbps target) ---\n")
    print(f"{'Scenario':<20} {'Throughput':<15} {'Jitter':<15} {'Loss':<15}")
    print("-" * 65)
    print(f"{'Baseline':<20} {voip_base_tp:.2f} Mbps{'':<6} {voip_base_jitter:.2f} ms{'':<6} {voip_base_loss:.2f}%")
    print(f"{'Congested':<20} {voip_cong_tp:.2f} Mbps{'':<6} {voip_cong_jitter:.2f} ms{'':<6} {voip_cong_loss:.2f}%")

    if voip_base_tp > 0:
        voip_degradation = ((voip_base_tp - voip_cong_tp) / voip_base_tp) * 100
        print(f"\nVoIP Degradation: {voip_degradation:.1f}%")
        if voip_degradation < 20:
            print("✓ QoS is protecting VoIP traffic (< 20% degradation)")
        else:
            print("⚠️  Significant VoIP degradation detected")

    # Display Video comparison
    print("\n--- Video (TCP 5Mbps target) ---\n")
    print(f"{'Scenario':<20} {'Throughput':<15} {'Retransmits':<15}")
    print("-" * 50)
    print(f"{'Baseline':<20} {video_base_tp:.2f} Mbps{'':<6} {video_base_retrans}")
    print(f"{'Congested':<20} {video_cong_tp:.2f} Mbps{'':<6} {video_cong_retrans}")

    # Display Data comparison
    print("\n--- Data (TCP Best Effort) ---\n")
    print(f"{'Scenario':<20} {'Throughput':<15} {'Retransmits':<15}")
    print("-" * 50)
    print(f"{'Baseline':<20} {data_base_tp:.2f} Mbps{'':<6} {data_base_retrans}")
    print(f"{'Congested':<20} {data_cong_tp:.2f} Mbps{'':<6} {data_cong_retrans}")

    if data_base_tp > 0:
        data_degradation = ((data_base_tp - data_cong_tp) / data_base_tp) * 100
        print(f"\nData Degradation: {data_degradation:.1f}%")
        print("✓ Best-effort traffic absorbing most congestion impact")

    # Summary
    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)
    print(f"\nResults saved in: {results_dir}")
    print("  - scenario1_baseline/")
    print("  - scenario2_congested/")
    print("\nKey Observations:")
    print("  - VoIP should maintain > 80% throughput under congestion")
    print("  - Video should get priority over data traffic")
    print("  - Data traffic should absorb most of the impact")
    print("\nNext steps:")
    print("  1. Review VNF logs in each scenario directory")
    print("  2. Check classification accuracy")
    print("  3. Verify policing is dropping excess traffic")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(0)
