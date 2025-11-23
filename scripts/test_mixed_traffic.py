import subprocess
import time
import json
import os
import sys
from datetime import datetime
from pathlib import Path


def run_command(cmd, capture=False):
    try:
        if capture:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return result.stdout
        else:
            subprocess.run(cmd, shell=True)
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def main():
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = Path(f"./test_results/mixed_{timestamp}")
    results_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("Mixed Traffic Test")
    print("All clients transmitting simultaneously")
    print("=" * 50)
    print(f"\nTest duration: {duration} seconds")
    print(f"Results: {results_dir}")
    print()

    print("🛑 Stopping existing iperf3 servers...")
    run_command("docker exec server pkill iperf3")
    time.sleep(1)
    print("🚀 Starting iperf3 servers...")
    run_command("docker exec -d server iperf3 -s -p 5004 -u")
    run_command("docker exec -d server iperf3 -s -p 8080")
    run_command("docker exec -d server iperf3 -s -p 5001")
    time.sleep(2)
    print("✓ Servers ready\n")

    print("Starting all traffic flows...")
    print("-" * 50)

    print("📞 Starting VoIP traffic (UDP 200Kbps)...")
    run_command(
        f'docker exec -d client_voip sh -c "iperf3 -c 10.0.0.100 -p 5004 -u -b 200K -t {duration} -l 160 -J > /tmp/voip_result.json 2>&1"')
    time.sleep(1)

    print("📹 Starting Video traffic (TCP 5Mbps)...")
    run_command(
        f'docker exec -d client_video sh -c "iperf3 -c 10.0.0.100 -p 8080 -b 5M -t {duration} -J > /tmp/video_result.json 2>&1"')
    time.sleep(1)

    print("💾 Starting Data traffic (TCP unlimited)...")
    run_command(
        f'docker exec -d client_data sh -c "iperf3 -c 10.0.0.100 -p 5001 -t {duration} -J > /tmp/data_result.json 2>&1"')

    print("✓ All traffic started\n")
    print("Test in progress...")
    print("Monitor logs: docker-compose logs -f vnf_classification\n")

    for i in range(1, duration + 1):
        print(f"\rElapsed: {i:2d}/{duration} seconds", end='', flush=True)
        time.sleep(1)
    print("\n")

    print("Waiting for clients to finish...")
    time.sleep(3)

    print("\n" + "=" * 50)
    print("Collecting Results...")
    print("=" * 50 + "\n")
    run_command(f'docker cp client_voip:/tmp/voip_result.json "{results_dir.resolve()}\\voip.json"')
    run_command(f'docker cp client_video:/tmp/video_result.json "{results_dir.resolve()}\\video.json"')
    run_command(f'docker cp client_data:/tmp/data_result.json "{results_dir.resolve()}\\data.json"')

    def parse_result(filename, traffic_type):
        filepath = results_dir / filename
        if not filepath.exists():
            print(f"  ⚠️  No results found")
            return

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            if traffic_type == "voip":
                bps = data.get('end', {}).get('sum', {}).get('bits_per_second', 0)
                jitter = data.get('end', {}).get('sum', {}).get('jitter_ms', 0)
                loss = data.get('end', {}).get('sum', {}).get('lost_percent', 0)

                print(f"  Throughput: {bps / 1e6:.2f} Mbps (target: 0.2 Mbps)")
                print(f"  Jitter: {jitter:.2f} ms (target: < 30 ms)")
                print(f"  Loss: {loss:.2f}% (target: < 1%)")
            else:
                sum_data = data.get('end', {}).get('sum_received', {})
                if not sum_data:
                    sum_data = data.get('end', {}).get('sum', {})

                bps = sum_data.get('bits_per_second', 0)
                retrans = data.get('end', {}).get('sum_sent', {}).get('retransmits', 0)

                target = "5 Mbps" if traffic_type == "video" else "best effort"
                print(f"  Throughput: {bps / 1e6:.2f} Mbps (target: {target})")
                print(f"  Retransmits: {retrans}")
        except:
            print(f"  ⚠️  Could not parse results")

    print("--- VoIP Results ---")
    parse_result("voip.json", "voip")

    print("\n--- Video Results ---")
    parse_result("video.json", "video")

    print("\n--- Data Results ---")
    parse_result("data.json", "data")

    # VNF Statistics
    print("\n" + "=" * 50)
    print("VNF Statistics")
    print("=" * 50)

    print("\n--- Classification VNF ---")
    log = run_command("docker exec vnf_classification tail -20 /logs/classification.log 2>/dev/null", capture=True)
    if log:
        lines = [l for l in log.split('\n') if any(w in l for w in ["CLASSIFIED", "Total", "VoIP", "Video", "Data"])]
        for line in lines[-10:]:
            print(line)

    print("\n--- Policing VNF ---")
    log = run_command("docker exec vnf_policing tail -20 /logs/policing.log 2>/dev/null", capture=True)
    if log:
        lines = [l for l in log.split('\n') if any(w in l for w in ["Stats", "passed", "dropped"])]
        for line in lines[-5:]:
            print(line)

    print("\n--- Monitoring VNF ---")
    log = run_command("docker exec vnf_monitoring tail -20 /logs/monitoring.log 2>/dev/null", capture=True)
    if log:
        lines = [l for l in log.split('\n') if any(w in l for w in ["Total", "Throughput", "Traffic"])]
        for line in lines[-10:]:
            print(line)

    print("\n📝 Saving VNF logs...")
    run_command(f"docker cp vnf_classification:/logs/classification.log \"{results_dir.resolve()}\\classification.log\"")
    run_command(f"docker cp vnf_policing:/logs/policing.log \"{results_dir.resolve()}\\policing.log\"")
    run_command(f"docker cp vnf_monitoring:/logs/monitoring.log \"{results_dir.resolve()}\\monitoring.log\"")

    print("\n" + "=" * 50)
    print("Test Complete!")
    print("=" * 50)
    print(f"\nResults saved in: {results_dir}")
    print("  - voip.json, video.json, data.json")
    print("  - classification.log, policing.log, monitoring.log")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(0)
