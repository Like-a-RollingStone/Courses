#!/usr/bin/env python3
import subprocess
import re
import matplotlib.pyplot as plt
import os

SIM_PATH = "./sim"
TRACES_DIR = "../ext_traces"
TRACES = ["spice.trace", "cc.trace", "tex.trace"]
BLOCK_SIZE = 4
CACHE_SIZES = [4 * (2 ** i) for i in range(19)]

def run_sim(cache_size, trace_file):
    assoc = cache_size // BLOCK_SIZE
    if assoc < 1:
        assoc = 1
    
    cmd = [
        SIM_PATH,
        "-bs", str(BLOCK_SIZE),
        "-is", str(cache_size),
        "-ds", str(cache_size),
        "-a", str(assoc),
        "-wb", "-wa",
        os.path.join(TRACES_DIR, trace_file)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        output = result.stdout
        
        inst_hit_rate = None
        data_hit_rate = None
        lines = output.split('\n')
        section = None
        for line in lines:
            if 'INSTRUCTIONS' in line:
                section = 'inst'
            elif 'DATA' in line:
                section = 'data'
            elif 'hit rate' in line:
                match = re.search(r'hit rate\s+([\d.]+)', line)
                if match:
                    rate = float(match.group(1))
                    if section == 'inst':
                        inst_hit_rate = rate
                    elif section == 'data':
                        data_hit_rate = rate
        
        return inst_hit_rate, data_hit_rate
    except Exception as e:
        print(f"Error running sim: {e}")
        return None, None

def find_working_set_size(sizes, hit_rates, threshold=0.99):
    max_rate = max(r for r in hit_rates if r is not None)
    for i, (size, rate) in enumerate(zip(sizes, hit_rates)):
        if rate is not None and rate >= max_rate * threshold:
            return size
    return sizes[-1]

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    code_dir = os.path.join(script_dir, "attachment", "code")
    os.chdir(code_dir)
    print(f"Working directory: {os.getcwd()}")
    
    results = {}
    
    for trace in TRACES:
        print(f"\n测试 {trace}...")
        inst_rates = []
        data_rates = []
        valid_sizes = []
        
        for size in CACHE_SIZES:
            inst_rate, data_rate = run_sim(size, trace)
            if inst_rate is not None and data_rate is not None:
                inst_rates.append(inst_rate)
                data_rates.append(data_rate)
                valid_sizes.append(size)
                print(f"  缓存大小: {size:>8}B, I-hit: {inst_rate:.4f}, D-hit: {data_rate:.4f}")
        
        results[trace] = {
            'sizes': valid_sizes,
            'inst_rates': inst_rates,
            'data_rates': data_rates
        }
    
    fig, axes = plt.subplots(2, 1, figsize=(12, 10))
    colors = {'spice.trace': 'blue', 'cc.trace': 'green', 'tex.trace': 'red'}
    markers = {'spice.trace': 'o', 'cc.trace': 's', 'tex.trace': '^'}
    all_inst = [r for t in TRACES for r in results[t]['inst_rates'] if r is not None]
    all_data = [r for t in TRACES for r in results[t]['data_rates'] if r is not None]
    inst_min = min(all_inst) - 0.01 if all_inst else 0
    inst_max = min(1.0, max(all_inst) + 0.01) if all_inst else 1.0
    data_min = min(all_data) - 0.01 if all_data else 0
    data_max = min(1.0, max(all_data) + 0.01) if all_data else 1.0
    ax1 = axes[0]
    for trace in TRACES:
        data = results[trace]
        label = trace.replace('.trace', '')
        ax1.semilogx(data['sizes'], data['inst_rates'], 
                     marker=markers[trace], color=colors[trace], 
                     label=label, linewidth=2, markersize=4, base=2)
    ax1.set_xlabel('Cache Size (Bytes)', fontsize=12)
    ax1.set_ylabel('Instruction Hit Rate', fontsize=12)
    ax1.set_title('Instruction Cache Hit Rate vs Cache Size', fontsize=14)
    ax1.legend(loc='best')
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(inst_min, inst_max)
    ax2 = axes[1]
    for trace in TRACES:
        data = results[trace]
        label = trace.replace('.trace', '')
        ax2.semilogx(data['sizes'], data['data_rates'], 
                     marker=markers[trace], color=colors[trace], 
                     label=label, linewidth=2, markersize=4, base=2)
    ax2.set_xlabel('Cache Size (Bytes)', fontsize=12)
    ax2.set_ylabel('Data Hit Rate', fontsize=12)
    ax2.set_title('Data Cache Hit Rate vs Cache Size', fontsize=14)
    ax2.legend(loc='best')
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(data_min, data_max)
    
    plt.tight_layout()
    plt.savefig('../../pics/exp2_1_workingset.png', dpi=150, bbox_inches='tight')
    print(f"\n图表已保存到 pics/exp2_1_workingset.png")
    print("\n=== 工作集大小估计 ===")
    for trace in TRACES:
        data = results[trace]
        inst_ws = find_working_set_size(data['sizes'], data['inst_rates'])
        data_ws = find_working_set_size(data['sizes'], data['data_rates'])
        print(f"{trace}:")
        print(f"  指令工作集: ~{inst_ws} bytes ({inst_ws/1024:.1f} KB)")
        print(f"  数据工作集: ~{data_ws} bytes ({data_ws/1024:.1f} KB)")

if __name__ == "__main__":
    main()
