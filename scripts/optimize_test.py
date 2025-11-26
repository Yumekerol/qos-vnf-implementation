# Test different policing configurations to analyze trade-off
import subprocess
import time
import json
import shutil
from pathlib import Path
from datetime import datetime


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


def backup_police_py():
    police_path = Path("./vnfs/policing/police.py")
    backup_path = Path("./vnfs/policing/police.py.backup")

    if police_path.exists() and not backup_path.exists():
        shutil.copy(police_path, backup_path)
        print(" Backed up police.py")
        return True
    elif backup_path.exists():
        print(" Backup already exists")
        return True
    else:
        print(" police.py not found!")
        return False


def restore_police_py():
    police_path = Path("./vnfs/policing/police.py")
    backup_path = Path("./vnfs/policing/police.py.backup")

    if backup_path.exists():
        shutil.copy(backup_path, police_path)
        print(" Restored original police.py")
        return True
    return False


def modify_police_config(config_name, voip_rate, video_rate, data_rate):
    police_path = Path("./vnfs/policing/police.py")

    if not police_path.exists():
        print("✗ police.py not found!")
        return False

    with open(police_path, 'r') as f:
        content = f.read()

    # Find and replace the bucket configuration
    # Current format:
    # 'voip': TokenBucket(rate=125000, capacity=250000),  # 1 Mbps

    lines = content.split('\n')
    new_lines = []

    for line in lines:
        if "'voip': TokenBucket(rate=" in line:
            new_lines.append(
                f"    'voip': TokenBucket(rate={voip_rate}, capacity={voip_rate * 2}),  # {voip_rate / 125000:.1f} Mbps")
        elif "'video': TokenBucket(rate=" in line:
            new_lines.append(
                f"    'video': TokenBucket(rate={video_rate}, capacity={video_rate * 2}),  # {video_rate / 125000:.1f} Mbps")
        elif "'data': TokenBucket(rate=" in line:
            new_lines.append(
                f"    'data': TokenBucket(rate={data_rate}, capacity={data_rate * 2}),  # {data_rate / 125000:.1f} Mbps")
        else:
            new_lines.append(line)

    with open(police_path, 'w') as f:
        f.write('\n'.join(new_lines))

    print(f"Modified police.py for config: {config_name}")
    print(f"  VoIP:  {voip_rate / 125000:.1f} Mbps")
    print(f"  Video: {video_rate / 125000:.1f} Mbps")
    print(f"  Data:  {data_rate / 125000:.1f} Mbps")

    return True


def rebuild_policing_vnf():
    print("\nRebuilding policing VNF...")

    run_command("docker-compose stop vnf_policing")
    time.sleep(2)
    run_command("docker-compose build vnf_policing")
    time.sleep(3)

    run_command("docker-compose up -d vnf_policing")
    time.sleep(5)

    out = run_command("docker ps | grep vnf_policing", capture=True)
    if out and "Up" in out:
        print(" Policing VNF restarted successfully")
        return True
    else:
        print(" Failed to restart policing VNF")
        return False


def clear_vnf_logs():
    print("  Clearing VNF logs...")
    vnfs = ["vnf_classification", "vnf_policing", "vnf_monitoring"]

    for vnf in vnfs:
        # keep file but empty content
        run_command(f"docker exec {vnf} sh -c '> /logs/classification.log' 2>/dev/null")
        run_command(f"docker exec {vnf} sh -c '> /logs/policing.log' 2>/dev/null")
        run_command(f"docker exec {vnf} sh -c '> /logs/monitoring.log' 2>/dev/null")

    time.sleep(1)
    print(" Logs cleared")


def run_test_scenario(config_name, results_dir, duration=30):
    scenario_dir = results_dir / config_name
    scenario_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 60}")
    print(f"Testing: {config_name}")
    print(f"{'=' * 60}")

    clear_vnf_logs()

    run_command("docker exec server pkill iperf3 2>/dev/null")
    time.sleep(2)

    print("Starting iperf3 servers...")
    run_command("docker exec -d server iperf3 -s -p 5004")  # VoIP (UDP)
    run_command("docker exec -d server iperf3 -s -p 8080")  # Video (TCP)
    run_command("docker exec -d server iperf3 -s -p 5001")  # Data (TCP)
    time.sleep(5)


    out = run_command("docker exec server ps aux | grep iperf3", capture=True)
    if "iperf3 -s" in out:
        print("✓ Servers running")
    else:
        print("⚠ Warning: Servers not running properly")


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


def analyze_config_results(results_dir, configs):
    print("\n" + "=" * 60)
    print("OPTIMIZATION RESULTS ANALYSIS")
    print("=" * 60)

    results = {}

    for config_name, _, _, _ in configs:
        config_dir = results_dir / config_name

        results[config_name] = {
            'voip_tp': parse_json_metric(config_dir / "voip.json", "voip_throughput"),
            'voip_jitter': parse_json_metric(config_dir / "voip.json", "voip_jitter"),
            'voip_loss': parse_json_metric(config_dir / "voip.json", "voip_loss"),
            'video_tp': parse_json_metric(config_dir / "video.json", "tcp_throughput"),
            'video_retrans': parse_json_metric(config_dir / "video.json", "tcp_retrans"),
            'data_tp': parse_json_metric(config_dir / "data.json", "tcp_throughput"),
            'data_retrans': parse_json_metric(config_dir / "data.json", "tcp_retrans"),
        }

    print("\n" + "=" * 60)
    print("VoIP Performance")
    print("=" * 60)
    print(f"{'Config':<25} {'Throughput':<15} {'Jitter':<12} {'Loss':<10}")
    print("-" * 62)

    for config_name in results:
        m = results[config_name]
        print(
            f"{config_name:<25} {m['voip_tp']:.3f} Mbps{'':<5} {m['voip_jitter']:.2f} ms{'':<3} {m['voip_loss']:.2f}%")

    print("\n" + "=" * 60)
    print("Video Performance")
    print("=" * 60)
    print(f"{'Config':<25} {'Throughput':<15} {'Retransmits':<12}")
    print("-" * 52)

    for config_name in results:
        m = results[config_name]
        print(f"{config_name:<25} {m['video_tp']:.2f} Mbps{'':<6} {m['video_retrans']}")

    print("\n" + "=" * 60)
    print("Data Performance")
    print("=" * 60)
    print(f"{'Config':<25} {'Throughput':<15} {'Retransmits':<12}")
    print("-" * 52)

    for config_name in results:
        m = results[config_name]
        print(f"{config_name:<25} {m['data_tp']:.2f} Mbps{'':<6} {m['data_retrans']}")

    print("\n" + "=" * 60)
    print("TRADE-OFF ANALYSIS")
    print("=" * 60)

    baseline = results.get('config_a_baseline')
    if baseline:
        print(f"\nBaseline (Config A):")
        print(f"  VoIP:  {baseline['voip_tp']:.3f} Mbps")
        print(f"  Video: {baseline['video_tp']:.2f} Mbps")
        print(f"  Data:  {baseline['data_tp']:.2f} Mbps")

        for config_name in results:
            if config_name == 'config_a_baseline':
                continue

            m = results[config_name]

            voip_change = ((m['voip_tp'] - baseline['voip_tp']) / baseline['voip_tp'] * 100) if baseline[
                                                                                                    'voip_tp'] > 0 else 0
            video_change = ((m['video_tp'] - baseline['video_tp']) / baseline['video_tp'] * 100) if baseline[
                                                                                                        'video_tp'] > 0 else 0
            data_change = ((m['data_tp'] - baseline['data_tp']) / baseline['data_tp'] * 100) if baseline[
                                                                                                    'data_tp'] > 0 else 0

            print(f"\n{config_name}:")
            print(f"  VoIP:  {m['voip_tp']:.3f} Mbps ({voip_change:+.1f}%)")
            print(f"  Video: {m['video_tp']:.2f} Mbps ({video_change:+.1f}%)")
            print(f"  Data:  {m['data_tp']:.2f} Mbps ({data_change:+.1f}%)")

            print(f"\n  Trade-offs:")
            if voip_change > 5:
                print(f"    VoIP benefits from higher limit (+{voip_change:.1f}%)")
            elif voip_change < -5:
                print(f"   VoIP suffers from lower limit ({voip_change:.1f}%)")

            if video_change > 5:
                print(f"    Video throughput improved (+{video_change:.1f}%)")
            elif video_change < -5:
                print(f"    Video throughput reduced ({video_change:.1f}%)")

            if data_change > 5:
                print(f"    Data gets more bandwidth (+{data_change:.1f}%)")
            elif data_change < -5:
                print(f"    Data gets less bandwidth ({data_change:.1f}%)")

    summary_path = results_dir / "optimization_summary.md"
    with open(summary_path, 'w') as f:
        f.write("# QoS Policing Optimization Analysis\n\n")
        f.write("## Tested Configurations\n\n")

        for config_name, voip, video, data in configs:
            f.write(f"### {config_name}\n")
            f.write(f"- VoIP: {voip / 125000:.1f} Mbps\n")
            f.write(f"- Video: {video / 125000:.1f} Mbps\n")
            f.write(f"- Data: {data / 125000:.1f} Mbps\n\n")

        f.write("## Results Summary\n\n")
        f.write("| Config | VoIP (Mbps) | Video (Mbps) | Data (Mbps) |\n")
        f.write("|--------|-------------|--------------|-------------|\n")

        for config_name in results:
            m = results[config_name]
            f.write(f"| {config_name} | {m['voip_tp']:.3f} | {m['video_tp']:.2f} | {m['data_tp']:.2f} |\n")

        f.write("\n## Key Findings\n\n")
        f.write("*(To be filled based on results)*\n\n")
        f.write("1. **Increasing limits:** Higher rate limits allow more throughput but reduce fairness\n")
        f.write("2. **Decreasing limits:** Lower limits enforce stricter QoS but cap performance\n")
        f.write("3. **Priority inversion:** Giving Data higher limit than Video breaks QoS guarantees\n")

    print(f"\n✓ Summary saved to: {summary_path}")


def main():
    print("=" * 60)
    print("QoS POLICING OPTIMIZATION TESTING")
    print("=" * 60)

    configs = [
        ("config_a_baseline", 125000, 1250000, 625000),  # 1, 10, 5 Mbps (current)
        ("config_b_generous", 250000, 2500000, 1250000),  # 2, 20, 10 Mbps
        ("config_c_restrictive", 62500, 625000, 312500),  # 0.5, 5, 2.5 Mbps
        ("config_d_inverted", 125000, 625000, 1250000),  # 1, 5, 10 Mbps (Data > Video)
    ]

    print(f"\nThis will test {len(configs)} different configurations:")
    for i, (name, voip, video, data) in enumerate(configs, 1):
        print(f"  {i}. {name}: VoIP={voip / 125000:.1f} Video={video / 125000:.1f} Data={data / 125000:.1f} Mbps")

    print(f"\nDuration: 30s per config")
    print(f"Total time: ~{len(configs) * 0.7:.0f} minutes")

    if not backup_police_py():
        print("\n✗ Cannot proceed without backup!")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = Path(f"./test_results/optimization_{timestamp}")
    results_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nResults directory: {results_dir}")

    input("\nPress Enter to start optimization testing...")

    try:
        for i, (config_name, voip_rate, video_rate, data_rate) in enumerate(configs, 1):
            print(f"\n\n{'#' * 60}")
            print(f"# CONFIG {i}/{len(configs)}: {config_name}")
            print(f"{'#' * 60}")

            if not modify_police_config(config_name, voip_rate, video_rate, data_rate):
                print("Failed to modify config, skipping...")
                continue

            if not rebuild_policing_vnf():
                print("Failed to rebuild VNF, skipping...")
                continue

            run_test_scenario(config_name, results_dir, duration=30)

            if i < len(configs):
                print(f"\nWaiting 5s before next config...")
                time.sleep(5)

        print("\n\nRestoring original configuration...")
        restore_police_py()
        rebuild_policing_vnf()

        analyze_config_results(results_dir, configs)

        print("\n" + "=" * 60)
        print("optimization test complete!")
        print("=" * 60)
        print(f"\nResults: {results_dir}")
        print("\nNext steps:")
        print("  1. Review optimization_summary.md")
        print("  2. Choose best configuration")

    except KeyboardInterrupt:
        print("\n\nTesting interrupted!")
        print("Restoring original configuration...")
        restore_police_py()
        rebuild_policing_vnf()

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()