import subprocess
import time
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
        print(f"Error running command: {e}")
        return None


def print_header(text):
    print("\n" + "=" * 50)
    print(text)
    print("=" * 50)


def print_section(text):
    print(f"\n--- {text} ---")


def main():
    print_header("Quick VNF Chain Test")

    print("\n🛑 Stopping existing iperf3 servers...")
    run_command("docker exec server pkill iperf3")
    time.sleep(1)

    print("🚀 Starting iperf3 servers...")
    run_command("docker exec -d server iperf3 -s -p 5004")  # VoIP
    run_command("docker exec -d server iperf3 -s -p 8080")   # Video
    run_command("docker exec -d server iperf3 -s -p 5001")   # Data
    time.sleep(2)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = Path(f"./test_results/quick_{timestamp}")
    results_dir.mkdir(parents=True, exist_ok=True)
    abs_results_dir = results_dir.resolve()

    print("✓ Servers started")

    print("\n🔍 Testing connectivity...")
    result = run_command("docker exec client_voip ping -c 3 -W 2 10.0.0.100", capture=True)
    if result and "3 received" in result:
        print("✓ Connectivity OK")
    else:
        print("✗ Connectivity FAILED - check VNF chain")
        input("Press Enter to exit...")
        sys.exit(1)

    def run_traffic_test(client, port, traffic_type, params):
        print_section(f"{traffic_type} Traffic Test")
        print(f"Client: {client} -> Server:10.0.0.100:{port}")
        cmd = f"docker exec {client} iperf3 -c 10.0.0.100 -p {port} {params} -t 10"
        run_command(cmd)
        input("\nPress Enter to continue to next test...")

    print_header("Starting Traffic Tests (10s each)")

    run_traffic_test("client_voip", "5004", "VoIP", "-u -b 200K -l 160")
    run_traffic_test("client_video", "8080", "Video", "-b 5M")
    run_traffic_test("client_data", "5001", "Data", "")

    print_header("VNF Statistics Summary")

    print_section("Classification VNF (last 15 lines)")
    log = run_command("docker exec vnf_classification tail -15 /logs/classification.log 2>/dev/null", capture=True)
    if log:
        for line in log.split('\n'):
            if any(word in line for word in ["CLASSIFIED", "Stats", "Total"]):
                print(line)

    print_section("Policing VNF (last 10 lines)")
    log = run_command("docker exec vnf_policing tail -10 /logs/policing.log 2>/dev/null", capture=True)
    if log:
        for line in log.split('\n'):
            if any(word in line for word in ["Stats", "passed", "dropped"]):
                print(line)

    print_section("Monitoring VNF (last 10 lines)")
    log = run_command("docker exec vnf_monitoring tail -10 /logs/monitoring.log 2>/dev/null", capture=True)
    if log:
        for line in log.split('\n'):
            if any(word in line for word in ["Total", "Throughput", "Traffic"]):
                print(line)

    print_header("Test Complete!")
    run_command(f"docker cp vnf_classification:/logs/classification.log \"{abs_results_dir}\\classification.log\"")
    run_command(f"docker cp vnf_policing:/logs/policing.log \"{abs_results_dir}\\policing.log\"")
    run_command(f"docker cp vnf_monitoring:/logs/monitoring.log \"{abs_results_dir}\\monitoring.log\"")
    print(f"Logs saved to {abs_results_dir}")

    print("\nTo view full logs:")
    print("  docker-compose logs -f vnf_classification")
    print("  docker-compose logs -f vnf_policing")
    print("  docker-compose logs -f vnf_monitoring")

    input("\nPress Enter to exit...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(0)