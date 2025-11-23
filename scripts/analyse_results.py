import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import sys

def load_iperf_json(filepath):
    if not filepath.exists():
        return None
    
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except:
        return None

def extract_voip_metrics(data):
    if not data:
        return {'throughput': 0, 'jitter': 0, 'loss': 0}
    
    end = data.get('end', {}).get('sum', {})
    return {
        'throughput': end.get('bits_per_second', 0) / 1e6,  # Mbps
        'jitter': end.get('jitter_ms', 0),
        'loss': end.get('lost_percent', 0)
    }

def extract_tcp_metrics(data):
    if not data:
        return {'throughput': 0, 'retransmits': 0}
    
    sum_received = data.get('end', {}).get('sum_received', {})
    if not sum_received:
        sum_received = data.get('end', {}).get('sum', {})
    
    sum_sent = data.get('end', {}).get('sum_sent', {})
    
    return {
        'throughput': sum_received.get('bits_per_second', 0) / 1e6,  # Mbps
        'retransmits': sum_sent.get('retransmits', 0)
    }

def analyze_scenario(scenario_path):
    voip_data = load_iperf_json(scenario_path / "voip.json")
    video_data = load_iperf_json(scenario_path / "video.json")
    data_data = load_iperf_json(scenario_path / "data.json")
    
    return {
        'voip': extract_voip_metrics(voip_data),
        'video': extract_tcp_metrics(video_data),
        'data': extract_tcp_metrics(data_data)
    }

def plot_throughput_comparison(results, output_dir):
    scenarios = list(results.keys())
    
    voip_tp = [results[s]['voip']['throughput'] for s in scenarios]
    video_tp = [results[s]['video']['throughput'] for s in scenarios]
    data_tp = [results[s]['data']['throughput'] for s in scenarios]
    
    x = np.arange(len(scenarios))
    width = 0.25
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    bars1 = ax.bar(x - width, voip_tp, width, label='VoIP', color='#2ecc71')
    bars2 = ax.bar(x, video_tp, width, label='Video', color='#3498db')
    bars3 = ax.bar(x + width, data_tp, width, label='Data', color='#e74c3c')
    
    ax.set_xlabel('Scenario', fontsize=12)
    ax.set_ylabel('Throughput (Mbps)', fontsize=12)
    ax.set_title('Throughput Comparison Across Scenarios', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(scenarios, rotation=45, ha='right')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'throughput_comparison.png', dpi=300)
    print(f"✓ Saved: throughput_comparison.png")
    plt.close()

def plot_voip_quality(results, output_dir):
    scenarios = list(results.keys())
    
    jitter = [results[s]['voip']['jitter'] for s in scenarios]
    loss = [results[s]['voip']['loss'] for s in scenarios]
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    ax1.bar(scenarios, jitter, color='#f39c12')
    ax1.axhline(y=30, color='r', linestyle='--', label='Acceptable limit (30ms)')
    ax1.set_ylabel('Jitter (ms)', fontsize=12)
    ax1.set_title('VoIP Jitter', fontsize=13, fontweight='bold')
    ax1.legend()
    ax1.grid(axis='y', alpha=0.3)
    
    # Loss plot
    ax2.bar(scenarios, loss, color='#e74c3c')
    ax2.axhline(y=1, color='r', linestyle='--', label='Acceptable limit (1%)')
    ax2.set_ylabel('Packet Loss (%)', fontsize=12)
    ax2.set_title('VoIP Packet Loss', fontsize=13, fontweight='bold')
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3)
    
    for ax in [ax1, ax2]:
        ax.set_xticklabels(scenarios, rotation=45, ha='right')
    
    plt.tight_layout()
    plt.savefig(output_dir / 'voip_quality.png', dpi=300)
    print(f"✓ Saved: voip_quality.png")
    plt.close()

def plot_tcp_retransmissions(results, output_dir):
    scenarios = list(results.keys())
    
    video_retrans = [results[s]['video']['retransmits'] for s in scenarios]
    data_retrans = [results[s]['data']['retransmits'] for s in scenarios]
    
    x = np.arange(len(scenarios))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    bars1 = ax.bar(x - width/2, video_retrans, width, label='Video', color='#3498db')
    bars2 = ax.bar(x + width/2, data_retrans, width, label='Data', color='#e74c3c')
    
    ax.set_xlabel('Scenario', fontsize=12)
    ax.set_ylabel('Retransmissions', fontsize=12)
    ax.set_title('TCP Retransmissions Comparison', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(scenarios, rotation=45, ha='right')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'tcp_retransmissions.png', dpi=300)
    print(f"✓ Saved: tcp_retransmissions.png")
    plt.close()

def generate_summary_table(results, output_file):
    with open(output_file, 'w') as f:
        f.write("# QoS Test Results Summary\n\n")
        
        f.write("## VoIP Performance (UDP 200Kbps)\n\n")
        f.write("| Scenario | Throughput (Mbps) | Jitter (ms) | Loss (%) |\n")
        f.write("|----------|-------------------|-------------|----------|\n")
        for scenario, data in results.items():
            voip = data['voip']
            f.write(f"| {scenario} | {voip['throughput']:.3f} | {voip['jitter']:.2f} | {voip['loss']:.2f} |\n")
        
        f.write("\n## Video Performance (TCP 5Mbps)\n\n")
        f.write("| Scenario | Throughput (Mbps) | Retransmits |\n")
        f.write("|----------|-------------------|-------------|\n")
        for scenario, data in results.items():
            video = data['video']
            f.write(f"| {scenario} | {video['throughput']:.2f} | {video['retransmits']} |\n")
        
        f.write("\n## Data Performance (TCP Best Effort)\n\n")
        f.write("| Scenario | Throughput (Mbps) | Retransmits |\n")
        f.write("|----------|-------------------|-------------|\n")
        for scenario, data in results.items():
            data_tcp = data['data']
            f.write(f"| {scenario} | {data_tcp['throughput']:.2f} | {data_tcp['retransmits']} |\n")
        
        f.write("\n## QoS Effectiveness Analysis\n\n")
        
        if 'baseline' in results and 'congested' in results:
            baseline_voip = results['baseline']['voip']['throughput']
            congested_voip = results['congested']['voip']['throughput']
            
            if baseline_voip > 0:
                voip_protection = (congested_voip / baseline_voip) * 100
                f.write(f"### VoIP Protection\n")
                f.write(f"- Baseline throughput: {baseline_voip:.3f} Mbps\n")
                f.write(f"- Congested throughput: {congested_voip:.3f} Mbps\n")
                f.write(f"- **Protection rate: {voip_protection:.1f}%**\n\n")
                
                if voip_protection >= 80:
                    f.write("✅ **PASS**: VoIP maintains >80% throughput under congestion\n\n")
                else:
                    f.write("❌ **FAIL**: VoIP degradation exceeds 20%\n\n")
    
    print(f"✓ Saved: summary_report.md")

def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_results.py <results_directory>")
        print("\nExample:")
        print("  python analyze_results.py ./test_results/comparison_20250119_143022")
        sys.exit(1)
    
    results_dir = Path(sys.argv[1])
    
    if not results_dir.exists():
        print(f"Error: Directory not found: {results_dir}")
        sys.exit(1)
    
    print("=" * 60)
    print("QoS Test Results Analysis")
    print("=" * 60)
    print(f"\nAnalyzing: {results_dir}\n")
    
    scenarios = {}
    for scenario_dir in sorted(results_dir.iterdir()):
        if scenario_dir.is_dir() and (scenario_dir / "voip.json").exists():
            scenario_name = scenario_dir.name.replace("scenario_", "").replace("_", " ").title()
            print(f"Processing: {scenario_name}")
            scenarios[scenario_name] = analyze_scenario(scenario_dir)
    
    if not scenarios:
        print("Error: No valid scenarios found!")
        sys.exit(1)
    
    print(f"\nFound {len(scenarios)} scenarios\n")
    
    print("Generating graphs...")
    plot_throughput_comparison(scenarios, results_dir)
    plot_voip_quality(scenarios, results_dir)
    plot_tcp_retransmissions(scenarios, results_dir)
    
    print("\nGenerating summary report...")
    generate_summary_table(scenarios, results_dir / "summary_report.md")
    
    print("\n" + "=" * 60)
    print("Analysis Complete!")
    print("=" * 60)
    print(f"\nGenerated files in {results_dir}:")
    print("  - throughput_comparison.png")
    print("  - voip_quality.png")
    print("  - tcp_retransmissions.png")
    print("  - summary_report.md")
    print("\nNext steps:")
    print("  1. Review graphs for QoS effectiveness")
    print("  2. Include these in your Phase 3 report")
    print("  3. Document optimization trade-offs")

if __name__ == "__main__":
    main()