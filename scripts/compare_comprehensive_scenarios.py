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

    print(f"Clearing existing network conditions...")
    for vnf in vnfs:
        run_command(f"docker exec {vnf} tc qdisc del dev eth0 root 2>/dev/null")

    time.sleep(1)

    if condition == "baseline":
        print("✓ Baseline: No network impairments")

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


def run_test(scenario_name, results_dir, duration=30):
    scenario_dir = results_dir / scenario_name
    scenario_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print(f"Running: {scenario_name}")
    print("=" * 60)

    run_command("docker exec server pkill iperf3 2>/dev/null")
    time.sleep(1)

    print("Starting iperf3 servers...")
    run_command("docker exec -d server iperf3 -s -p 5004 -u")  # VoIP (UDP)
    run_command("docker exec -d server iperf3 -s -p 8080")  # Video (TCP)
    run_command("docker exec -d server iperf3 -s -p 5001")  # Data (TCP)
    time.sleep(2)

    print(f"Starting mixed traffic ({duration} seconds)...")

    run_command(
        f'docker exec -d client_voip sh -c "iperf3 -c 10.0.0.100 -p 5004 -u -b 200K -t {duration} -l 160 -J > /tmp/voip.json 2>&1"')
    run_command(
        f'docker exec -d client_video sh -c "iperf3 -c 10.0.0.100 -p 8080 -b 5M -t {duration} -J > /tmp/video.json 2>&1"')
    run_command(
        f'docker exec -d client_data sh -c "iperf3 -c 10.0.0.100 -p 5001 -t {duration} -J > /tmp/data.json 2>&1"')

    for i in range(1, duration + 1):
        print(f"\r  Progress: {i:2d}/{duration} seconds", end='', flush=True)
        time.sleep(1)
    print()

    time.sleep(3)

    print("  Collecting results...")
    run_command(f'docker cp client_voip:/tmp/voip.json "{scenario_dir.resolve()}/voip.json"')
    run_command(f'docker cp client_video:/tmp/video.json "{scenario_dir.resolve()}/video.json"')
    run_command(f'docker cp client_data:/tmp/data.json "{scenario_dir.resolve()}/data.json"')
    run_command(f'docker cp vnf_classification:/logs/classification.log "{scenario_dir.resolve()}/classification.log"')
    run_command(f'docker cp vnf_policing:/logs/policing.log "{scenario_dir.resolve()}/policing.log"')
    run_command(f'docker cp vnf_monitoring:/logs/monitoring.log "{scenario_dir.resolve()}/monitoring.log"')

    print(f"  ✓ Results saved to {scenario_dir.name}")


def parse_json_metric(filepath, metric_type):
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


def display_scenario_results(scenario_name, scenario_dir):
    print(f"\n--- {scenario_name} ---")

    voip_tp = parse_json_metric(scenario_dir / "voip.json", "voip_throughput")
    voip_jitter = parse_json_metric(scenario_dir / "voip.json", "voip_jitter")
    voip_loss = parse_json_metric(scenario_dir / "voip.json", "voip_loss")

    video_tp = parse_json_metric(scenario_dir / "video.json", "tcp_throughput")
    video_retrans = parse_json_metric(scenario_dir / "video.json", "tcp_retrans")

    data_tp = parse_json_metric(scenario_dir / "data.json", "tcp_throughput")
    data_retrans = parse_json_metric(scenario_dir / "data.json", "tcp_retrans")

    print(f"VoIP:  {voip_tp:.3f} Mbps | Jitter: {voip_jitter:.2f} ms | Loss: {voip_loss:.2f}%")
    print(f"Video: {video_tp:.2f} Mbps | Retransmits: {video_retrans}")
    print(f"Data:  {data_tp:.2f} Mbps | Retransmits: {data_retrans}")


def analyze_all_results(results_dir, scenarios):
    print("\n" + "=" * 60)
    print("COMPREHENSIVE RESULTS ANALYSIS")
    print("=" * 60)
    all_metrics = {}
    for scenario_name, _ in scenarios:
        scenario_dir = results_dir / scenario_name

        all_metrics[scenario_name] = {
            'voip_tp': parse_json_metric(scenario_dir / "voip.json", "voip_throughput"),
            'voip_jitter': parse_json_metric(scenario_dir / "voip.json", "voip_jitter"),
            'voip_loss': parse_json_metric(scenario_dir / "voip.json", "voip_loss"),
            'video_tp': parse_json_metric(scenario_dir / "video.json", "tcp_throughput"),
            'video_retrans': parse_json_metric(scenario_dir / "video.json", "tcp_retrans"),
            'data_tp': parse_json_metric(scenario_dir / "data.json", "tcp_throughput"),
            'data_retrans': parse_json_metric(scenario_dir / "data.json", "tcp_retrans"),
        }

    print("\n" + "=" * 60)
    print("VoIP Performance (UDP 200Kbps target)")
    print("=" * 60)
    print(f"{'Scenario':<25} {'Throughput':<15} {'Jitter':<12} {'Loss':<10}")
    print("-" * 62)

    for scenario_name in all_metrics:
        m = all_metrics[scenario_name]
        print(
            f"{scenario_name:<25} {m['voip_tp']:.3f} Mbps{'':<5} {m['voip_jitter']:.2f} ms{'':<3} {m['voip_loss']:.2f}%")

    print("\n" + "=" * 60)
    print("Video Performance (TCP 5Mbps target)")
    print("=" * 60)
    print(f"{'Scenario':<25} {'Throughput':<15} {'Retransmits':<12}")
    print("-" * 52)

    for scenario_name in all_metrics:
        m = all_metrics[scenario_name]
        print(f"{scenario_name:<25} {m['video_tp']:.2f} Mbps{'':<6} {m['video_retrans']}")

    print("\n" + "=" * 60)
    print("Data Performance (TCP Best Effort)")
    print("=" * 60)
    print(f"{'Scenario':<25} {'Throughput':<15} {'Retransmits':<12}")
    print("-" * 52)

    for scenario_name in all_metrics:
        m = all_metrics[scenario_name]
        print(f"{scenario_name:<25} {m['data_tp']:.2f} Mbps{'':<6} {m['data_retrans']}")

    print("\n" + "=" * 60)
    print("QoS EFFECTIVENESS ANALYSIS")
    print("=" * 60)

    baseline_name = scenarios[0][0]
    baseline = all_metrics[baseline_name]

    print(f"\nBaseline: {baseline_name}")
    print(f"  VoIP:  {baseline['voip_tp']:.3f} Mbps")
    print(f"  Video: {baseline['video_tp']:.2f} Mbps")
    print(f"  Data:  {baseline['data_tp']:.2f} Mbps")

    print("\n--- Degradation Analysis ---\n")

    for scenario_name in list(all_metrics.keys())[1:]:  
        m = all_metrics[scenario_name]

        voip_degradation = ((baseline['voip_tp'] - m['voip_tp']) / baseline['voip_tp'] * 100) if baseline[
                                                                                                     'voip_tp'] > 0 else 0
        video_degradation = ((baseline['video_tp'] - m['video_tp']) / baseline['video_tp'] * 100) if baseline[
                                                                                                         'video_tp'] > 0 else 0
        data_degradation = ((baseline['data_tp'] - m['data_tp']) / baseline['data_tp'] * 100) if baseline[
                                                                                                     'data_tp'] > 0 else 0

        print(f"{scenario_name}:")
        print(
            f"  VoIP degradation:  {voip_degradation:>6.1f}% {'✓ PROTECTED' if voip_degradation < 20 else '⚠ IMPACTED'}")
        print(f"  Video degradation: {video_degradation:>6.1f}%")
        print(f"  Data degradation:  {data_degradation:>6.1f}%")
        print()

    # QoS Success Criteria
    print("=" * 60)
    print("QoS SUCCESS CRITERIA")
    print("=" * 60)
    print("\n✓ Target: VoIP maintains > 80% throughput under stress")
    print("✓ Target: Video prioritized over Data traffic")
    print("✓ Target: Data absorbs most congestion impact")
    print()

    worst_scenario = list(all_metrics.keys())[-1]  
    worst = all_metrics[worst_scenario]

    voip_retention = (worst['voip_tp'] / baseline['voip_tp'] * 100) if baseline['voip_tp'] > 0 else 0

    print(f"Worst case scenario: {worst_scenario}")
    print(f"  VoIP retention: {voip_retention:.1f}%")

    if voip_retention >= 80:
        print("  ✅ PASS: QoS successfully protects VoIP traffic")
    elif voip_retention >= 60:
        print("  ⚠️  PARTIAL: VoIP partially protected (60-80%)")
    else:
        print("  ❌ FAIL: VoIP severely impacted (< 60%)")


def main():
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

    print("=" * 60)
    print("COMPREHENSIVE QoS TESTING SUITE")
    print("=" * 60)
    print(f"\nThis will run {len(scenarios)} test scenarios:")
    for i, (name, _) in enumerate(scenarios, 1):
        print(f"  {i:2d}. {name}")

    print(f"\nDuration: 30 seconds per scenario")
    print(f"Total time: ~{len(scenarios) * 0.6:.0f} minutes")
    print(f"Results: {results_dir}")

    input("\nPress Enter to start comprehensive testing...")

    for i, (scenario_name, condition) in enumerate(scenarios, 1):
        print(f"\n\n{'#' * 60}")
        print(f"# SCENARIO {i}/{len(scenarios)}")
        print(f"{'#' * 60}")

        apply_network_condition(condition)
        run_test(scenario_name, results_dir)

        if i < len(scenarios):
            print(f"\nWaiting 5 seconds before next scenario...")
            time.sleep(5)

    print("\n\nResetting network conditions...")
    apply_network_condition("baseline")

    analyze_all_results(results_dir, scenarios)

    print("\n" + "=" * 60)
    print("TESTING COMPLETE")
    print("=" * 60)
    print(f"\nResults saved in: {results_dir}")
    print("\nGenerated files:")
    for scenario_name, _ in scenarios:
        print(f"  - {scenario_name}/")

    print("\n" + "=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    print("\n1. Generate graphs:")
    print(f"   python analyze_results.py {results_dir}")
    print("\n2. Review VNF logs in each scenario directory")
    print("\n3. Document findings in Phase 3 report")
    print("\n4. Experiment with VNF parameter optimization")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        print("Resetting network conditions...")
        apply_network_condition("baseline")
        sys.exit(0)