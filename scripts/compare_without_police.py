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
    print("CHECKING PREREQUISITES")
    print("=" * 60)

    containers = ["client_voip", "client_video", "client_data", "server",
                  "vnf_classification", "vnf_policing", "vnf_monitoring"]

    print("\n1. Checking containers...")
    for container in containers:
        result = run_command(f"docker ps --filter name={container} --format '{{{{.Names}}}}'", capture=True)
        if container in result:
            print(f"  [OK] {container} is running")
        else:
            print(f"  [FAIL] {container} is NOT running!")
            return False

    print("\n [OK] All prerequisites OK!")
    return True


def disable_policing_vnf():
    print("\n" + "=" * 60)
    print("DISABLING POLICING VNF")
    print("=" * 60)

    run_command("docker exec vnf_policing pkill -9 python3 2>/dev/null")
    time.sleep(2)

    run_command("docker exec vnf_policing iptables-legacy -F")
    run_command("docker exec vnf_policing iptables-legacy -X")

    run_command("docker exec vnf_policing sysctl -w net.ipv4.ip_forward=1")

    print(" [OK] Policing VNF bypassed - traffic flows directly")
    time.sleep(2)


def enable_policing_vnf():
    print("\n" + "=" * 60)
    print("ENABLING POLICING VNF")
    print("=" * 60)

    run_command("docker exec -d vnf_policing sh /scripts/forward.sh")
    time.sleep(2)
    run_command("docker exec -d vnf_policing python3 /app/police.py")

    print(" [OK] Policing VNF re-enabled")
    time.sleep(3)


def run_test(scenario_name, results_dir, duration=30, policing_enabled=True):
    scenario_dir = results_dir / scenario_name
    scenario_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print(f"RUNNING TEST: {scenario_name}")
    print(f"Policing: {'ENABLED' if policing_enabled else 'DISABLED'}")
    print("=" * 60)

    print("Cleaning up old iperf3 processes...")
    containers_to_clean = ["server", "client_voip", "client_video", "client_data"]
    for container in containers_to_clean:
        run_command(f"docker exec {container} pkill -9 iperf3 2>/dev/null")
    time.sleep(3)

    print("\nStarting iperf3 servers...")
    run_command("docker exec -d server iperf3 -s -p 5004 -1")
    run_command("docker exec -d server iperf3 -s -p 8080 -1")
    run_command("docker exec -d server iperf3 -s -p 5001 -1")
    time.sleep(3)

    print(f"\nStarting traffic ({duration}s test)")
    print("=" * 60)

    print("VoIP (UDP 150Kbps) starting...")
    run_command(
        f'docker exec -d client_voip sh -c "iperf3 -c 10.0.0.100 -p 5004 -u -b 150K -t {duration} -l 160 -J > /tmp/voip.json 2>&1"')
    time.sleep(5)

    print("Video (TCP 3Mbps) starting...")
    run_command(
        f'docker exec -d client_video sh -c "iperf3 -c 10.0.0.100 -p 8080 -b 3M -t {duration} -J > /tmp/video.json 2>&1"')
    time.sleep(3)

    print("Data (TCP 20Mbps) starting...")
    run_command(
        f'docker exec -d client_data sh -c "iperf3 -c 10.0.0.100 -p 5001 -b 20M -t {duration} -J > /tmp/data.json 2>&1"')

    print("\nTest running...")
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
    ]

    for container, src, dst in files_to_collect:
        target = scenario_dir / dst
        run_command(f'docker cp {container}:{src} "{target.resolve()}"', capture=True)

        if target.exists() and target.stat().st_size > 0:
            print(f"  [OK] {dst}: {target.stat().st_size} bytes")
        else:
            print(f"  [FAIL] {dst}: EMPTY or FAILED")

    print(f"Test completed: {scenario_name}\n")


def main():
    if not check_prerequisites():
        print("\nPrerequisites check failed!")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = Path(f"./test_results/policing_comparison_{timestamp}")
    results_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("POLICING VNF EFFECTIVENESS TEST")
    print("=" * 60)
    print("\nThis test compares network performance WITH and WITHOUT policing")
    print(f"Results will be saved to: {results_dir}")

    input("\nPress Enter to start testing...")

    print("\n" + "#" * 60)
    print("# TEST 1/2: BASELINE WITH POLICING")
    print("#" * 60)
    run_test("scenario1_baseline_with_policing", results_dir, duration=30, policing_enabled=True)

    time.sleep(5)

    print("\n" + "#" * 60)
    print("# TEST 2/2: BASELINE WITHOUT POLICING")
    print("#" * 60)
    disable_policing_vnf()
    run_test("scenario2_baseline_without_policing", results_dir, duration=30, policing_enabled=False)

    enable_policing_vnf()

    print("\n" + "=" * 60)
    print("TESTING COMPLETE!")
    print("=" * 60)
    print(f"\nResults saved in: {results_dir}")
    print("\nNext steps:")
    print(f"  1. Analyze results:")
    print(f"     python analyze_policing_comparison.py {results_dir}")
    print(f"  2. Review generated comparison graphs")
    print(f"  3. Document findings in Phase 3 report")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        print("Re-enabling policing VNF...")
        enable_policing_vnf()
        sys.exit(0)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)