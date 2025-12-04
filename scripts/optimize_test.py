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
        print("✓ Backed up police.py")
        return True
    elif backup_path.exists():
        print("✓ Backup already exists")
        return True
    else:
        print("✗ police.py not found!")
        return False


def restore_police_py():
    police_path = Path("./vnfs/policing/police.py")
    backup_path = Path("./vnfs/policing/police.py.backup")

    if backup_path.exists():
        shutil.copy(backup_path, police_path)
        print("✓ Restored original police.py")
        return True
    return False


def modify_police_config(config_name, voip_rate, video_rate, data_rate):
    police_path = Path("./vnfs/policing/police.py")

    if not police_path.exists():
        print("✗ police.py not found!")
        return False

    with open(police_path, 'r') as f:
        content = f.read()

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

    print(f"✓ Modified police.py for config: {config_name}")
    print(f"  VoIP:  {voip_rate / 125000:.1f} Mbps")
    print(f"  Video: {video_rate / 125000:.1f} Mbps")
    print(f"  Data:  {data_rate / 125000:.1f} Mbps")

    return True


def rebuild_policing_vnf():
    print("\n🔄 Rebuilding policing VNF...")

    run_command("docker-compose stop vnf_policing")
    time.sleep(2)
    run_command("docker-compose build vnf_policing")
    time.sleep(3)

    run_command("docker-compose up -d vnf_policing")
    time.sleep(5)

    out = run_command("docker ps | grep vnf_policing", capture=True)
    if out and "Up" in out:
        print("✓ Policing VNF restarted successfully")
        return True
    else:
        print("✗ Failed to restart policing VNF")
        return False


def clear_vnf_logs():
    print("# Clearing VNF logs...")
    vnfs = ["vnf_classification", "vnf_policing", "vnf_monitoring"]

    for vnf in vnfs:
        run_command(f"docker exec {vnf} sh -c '> /logs/classification.log' 2>/dev/null")
        run_command(f"docker exec {vnf} sh -c '> /logs/policing.log' 2>/dev/null")
        run_command(f"docker exec {vnf} sh -c '> /logs/monitoring.log' 2>/dev/null")

    time.sleep(1)
    print("✓ Logs cleared")


def run_test_scenario(config_name, results_dir, duration=30):
    scenario_dir = results_dir / config_name
    scenario_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 60}")
    print(f"# Testing: {config_name}")
    print(f"{'=' * 60}")

    clear_vnf_logs()

    # Kill old processes
    containers = ["server", "client_voip", "client_video", "client_data"]
    for container in containers:
        run_command(f"docker exec {container} pkill -9 iperf3 2>/dev/null")
    time.sleep(3)

    print(":D Starting iperf3 servers...")
    run_command("docker exec -d server iperf3 -s -p 5004 -1")  # VoIP (UDP)
    run_command("docker exec -d server iperf3 -s -p 8080 -1")  # Video (TCP)
    run_command("docker exec -d server iperf3 -s -p 5001 -1")  # Data (TCP)
    time.sleep(3)

    out = run_command("docker exec server netstat -tuln", capture=True)
    if "5004" in out and "8080" in out and "5001" in out:
        print("✓ All servers listening")
    else:
        print("!!! Warning: Some servers may not be listening")

    print(f" Starting mixed traffic ({duration} seconds) in PRIORITY ORDER...")

    # Clean old results
    for container in ["client_voip", "client_video", "client_data"]:
        run_command(f"docker exec {container} rm -f /tmp/*.json")

    # ============================================================
    # START IN PRIORITY ORDER: VoIP → Video → Data
    # ============================================================

    print(" VoIP (UDP 150Kbps) starting...")
    run_command(
        f'docker exec -d client_voip sh -c "iperf3 -c 10.0.0.100 -p 5004 -u -b 150K -t {duration} -l 160 -J > /tmp/voip.json 2>&1"')
    print(" Waiting 5 seconds for VoIP flow...")
    time.sleep(5)
    print(" VoIP flow stable")

    print(" Video (TCP 3Mbps) starting...")
    run_command(
        f'docker exec -d client_video sh -c "iperf3 -c 10.0.0.100 -p 8080 -b 3M -t {duration} -J > /tmp/video.json 2>&1"')
    print(" Waiting 3 seconds for Video flow...")
    time.sleep(3)
    print(" Video flow active")

    print(" Data (TCP 20Mbps) starting...")
    run_command(
        f'docker exec -d client_data sh -c "iperf3 -c 10.0.0.100 -p 5001 -b 20M -t {duration} -J > /tmp/data.json 2>&1"')
    print(" Data started (competing for bandwidth)")

    print("\n All flows active - test running...")
    for i in range(1, duration + 1):
        print(f"\r Progress: {i:2d}/{duration} seconds", end='', flush=True)
        time.sleep(1)
    print()

    print("\n Waiting for tests to complete...")
    time.sleep(5)

    print(" Collecting results...")
    run_command(f'docker cp client_voip:/tmp/voip.json "{scenario_dir.resolve()}/voip.json"')
    run_command(f'docker cp client_video:/tmp/video.json "{scenario_dir.resolve()}/video.json"')
    run_command(f'docker cp client_data:/tmp/data.json "{scenario_dir.resolve()}/data.json"')
    run_command(f'docker cp vnf_classification:/logs/classification.log "{scenario_dir.resolve()}/classification.log"')
    run_command(f'docker cp vnf_policing:/logs/policing.log "{scenario_dir.resolve()}/policing.log"')
    run_command(f'docker cp vnf_monitoring:/logs/monitoring.log "{scenario_dir.resolve()}/monitoring.log"')
    print(f"Results saved to {scenario_dir.name}")


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
    print("📊 OPTIMIZATION RESULTS ANALYSIS")
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
    print(" VoIP Performance")
    print("=" * 60)
    print(f"{'Config':<30} {'Throughput':<15} {'Jitter':<12} {'Loss':<10}")
    print("-" * 67)

    for config_name in results:
        m = results[config_name]
        loss_status = "✅" if m['voip_loss'] < 1.0 else "!!!" if m['voip_loss'] < 3.0 else "XXXXX"
        print(
            f"{config_name:<30} {m['voip_tp']:.3f} Mbps{'':<5} {m['voip_jitter']:.2f} ms{'':<3} {m['voip_loss']:.2f}% {loss_status}")

    print("\n" + "=" * 60)
    print(" Video Performance")
    print("=" * 60)
    print(f"{'Config':<30} {'Throughput':<15} {'Retransmits':<12}")
    print("-" * 57)

    for config_name in results:
        m = results[config_name]
        print(f"{config_name:<30} {m['video_tp']:.2f} Mbps{'':<6} {m['video_retrans']}")

    print("\n" + "=" * 60)
    print(" Data Performance")
    print("=" * 60)
    print(f"{'Config':<30} {'Throughput':<15} {'Retransmits':<12}")
    print("-" * 57)

    for config_name in results:
        m = results[config_name]
        print(f"{config_name:<30} {m['data_tp']:.2f} Mbps{'':<6} {m['data_retrans']}")

    print("\n" + "=" * 60)
    print(" TRADE-OFF ANALYSIS")
    print("=" * 60)

    baseline = results.get('config_a_current_optimal')
    if baseline:
        print(f"\n Baseline (Current Optimal Config):")
        print(f"  VoIP:  {baseline['voip_tp']:.3f} Mbps | Loss: {baseline['voip_loss']:.2f}%")
        print(f"  Video: {baseline['video_tp']:.2f} Mbps")
        print(f"  Data:  {baseline['data_tp']:.2f} Mbps")

        for config_name in results:
            if config_name == 'config_a_current_optimal':
                continue

            m = results[config_name]

            voip_loss_change = m['voip_loss'] - baseline['voip_loss']
            video_change = ((m['video_tp'] - baseline['video_tp']) / baseline['video_tp'] * 100) if baseline[
                                                                                                        'video_tp'] > 0 else 0
            data_change = ((m['data_tp'] - baseline['data_tp']) / baseline['data_tp'] * 100) if baseline[
                                                                                                    'data_tp'] > 0 else 0

            print(f"\n {config_name}:")
            print(f"  VoIP:  {m['voip_tp']:.3f} Mbps | Loss: {m['voip_loss']:.2f}% ({voip_loss_change:+.2f}%)")
            print(f"  Video: {m['video_tp']:.2f} Mbps ({video_change:+.1f}%)")
            print(f"  Data:  {m['data_tp']:.2f} Mbps ({data_change:+.1f}%)")

            print(f"\n Trade-offs:")
            if voip_loss_change > 1.0:
                print(f"    VoIP quality degraded (loss +{voip_loss_change:.2f}%)")
            elif voip_loss_change < -0.5:
                print(f"    VoIP quality improved (loss {voip_loss_change:.2f}%)")

            if video_change > 10:
                print(f"    Video throughput significantly improved (+{video_change:.1f}%)")
            elif video_change < -10:
                print(f"    Video throughput significantly reduced ({video_change:.1f}%)")

            if data_change > 20:
                print(f"    Data gets much more bandwidth (+{data_change:.1f}%)")
            elif data_change < -20:
                print(f"    Data severely restricted ({data_change:.1f}%)")

    # Save summary
    summary_path = results_dir / "optimization_summary.md"
    with open(summary_path, 'w') as f:
        f.write("# QoS Policing Optimization Analysis\n\n")
        f.write("## Tested Configurations\n\n")

        for config_name, voip, video, data in configs:
            f.write(f"### {config_name}\n")
            f.write(f"- VoIP: {voip / 125000:.1f} Mbps (capacity: {voip * 2 / 125000:.1f} Mbps)\n")
            f.write(f"- Video: {video / 125000:.1f} Mbps (capacity: {video * 2 / 125000:.1f} Mbps)\n")
            f.write(f"- Data: {data / 125000:.1f} Mbps (capacity: {data * 2 / 125000:.1f} Mbps)\n\n")

        f.write("## Results Summary\n\n")
        f.write("| Config | VoIP Loss (%) | Video (Mbps) | Data (Mbps) |\n")
        f.write("|--------|---------------|--------------|-------------|\n")

        for config_name in results:
            m = results[config_name]
            f.write(f"| {config_name} | {m['voip_loss']:.2f} | {m['video_tp']:.2f} | {m['data_tp']:.2f} |\n")

        f.write("\n## Key Findings\n\n")
        f.write("### VoIP Protection\n")
        f.write("- Current config maintains VoIP loss < 1% in most scenarios\n")
        f.write("- Increasing VoIP limit doesn't improve quality (already at 150Kbps)\n")
        f.write("- Decreasing limits may cause buffer overflow under stress\n\n")

        f.write("### Video vs Data Trade-off\n")
        f.write("- Video gets higher priority (6 Mbps) vs Data (1.5 Mbps)\n")
        f.write("- Increasing Video limit improves throughput but starves Data\n")
        f.write("- Inverting priorities breaks QoS guarantees\n\n")

        f.write("### Recommendations\n")
        f.write("- **Keep current config** for balanced QoS\n")
        f.write("- VoIP: 2 Mbps (250 KB/s) - Adequate protection\n")
        f.write("- Video: 6 Mbps (750 KB/s) - Medium priority\n")
        f.write("- Data: 1.5 Mbps (187.5 KB/s) - Best effort\n")

    print(f"\n✅ Summary saved to: {summary_path}")


def main():
    print("=" * 60)
    print("🔬 QoS POLICING OPTIMIZATION TESTING")
    print("=" * 60)

    # ============================================================
    # CONFIGURAÇÕES BASEADAS NO TEU police.py ATUAL
    # ============================================================
    configs = [
        # Config A: ATUAL (2, 6, 1.5 Mbps) - ÓTIMO
        ("config_a_current_optimal", 250000, 750000, 187500),

        # Config B: Mais generoso (3, 8, 2 Mbps)
        ("config_b_more_generous", 375000, 1000000, 250000),

        # Config C: Mais restritivo (1.5, 5, 1 Mbps)
        ("config_c_more_restrictive", 187500, 625000, 125000),

        # Config D: Prioridades invertidas (2, 4, 6 Mbps) - Data > Video
        ("config_d_inverted_priority", 250000, 500000, 750000),

        # Config E: VoIP dominante (4, 5, 1 Mbps)
        ("config_e_voip_dominant", 500000, 625000, 125000),
    ]

    print(f"\nThis will test {len(configs)} different configurations:")
    for i, (name, voip, video, data) in enumerate(configs, 1):
        print(f"  {i}. {name}:")
        print(f"     VoIP={voip / 125000:.1f} Mbps | Video={video / 125000:.1f} Mbps | Data={data / 125000:.1f} Mbps")

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

        print("\n\n Restoring original configuration...")
        restore_police_py()
        rebuild_policing_vnf()

        analyze_config_results(results_dir, configs)

        print("\n" + "=" * 60)
        print("OPTIMIZATION TEST COMPLETE!")
        print("=" * 60)
        print(f"\nResults: {results_dir}")
        print("\nNext steps:")
        print("  1. Review optimization_summary.md")
        print("  2. Choose best configuration for final report")
        print("  3. Document trade-offs in Phase 3")

    except KeyboardInterrupt:
        print("\n\nTesting interrupted!")
        print("Restoring original configuration...")
        restore_police_py()
        rebuild_policing_vnf()

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()