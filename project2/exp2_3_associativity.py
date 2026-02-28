#!/usr/bin/env python3
import subprocess
import re
import matplotlib.pyplot as plt
import os

SIM_PATH = "./sim"
TRACES_DIR = "../ext_traces"
TRACES = ["spice.trace", "cc.trace", "tex.trace"]
CACHE_SIZE = 8192
BLOCK_SIZE = 128
ASSOCIATIVITIES = [1, 2, 4, 8, 16, 32, 64]

def run_sim(assoc, trace_file):
    cmd = [
        SIM_PATH,
        "-bs", str(BLOCK_SIZE),
        "-is", str(CACHE_SIZE),
        "-ds", str(CACHE_SIZE),
        "-a", str(assoc),
        "-wb", "-wa",
        os.path.join(TRACES_DIR, trace_file)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
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
        valid_assocs = []
        
        for assoc in ASSOCIATIVITIES:
            inst_rate, data_rate = run_sim(assoc, trace)
            if inst_rate is not None and data_rate is not None:
                inst_rates.append(inst_rate)
                data_rates.append(data_rate)
                valid_assocs.append(assoc)
                print(f"  相联度: {assoc:>2}, I-hit: {inst_rate:.4f}, D-hit: {data_rate:.4f}")
        
        results[trace] = {
            'assocs': valid_assocs,
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
        ax1.semilogx(data['assocs'], data['inst_rates'], 
                     marker=markers[trace], color=colors[trace], 
                     label=label, linewidth=2, markersize=8, base=2)
    ax1.set_xlabel('Associativity', fontsize=12)
    ax1.set_ylabel('Instruction Hit Rate', fontsize=12)
    ax1.set_title('Instruction Cache Hit Rate vs Associativity (8KB, 128B block)', fontsize=14)
    ax1.legend(loc='best')
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(inst_min, inst_max)
    ax1.set_xticks(ASSOCIATIVITIES)
    ax1.set_xticklabels([str(a) for a in ASSOCIATIVITIES])
    ax2 = axes[1]
    for trace in TRACES:
        data = results[trace]
        label = trace.replace('.trace', '')
        ax2.semilogx(data['assocs'], data['data_rates'], 
                     marker=markers[trace], color=colors[trace], 
                     label=label, linewidth=2, markersize=8, base=2)
    ax2.set_xlabel('Associativity', fontsize=12)
    ax2.set_ylabel('Data Hit Rate', fontsize=12)
    ax2.set_title('Data Cache Hit Rate vs Associativity (8KB, 128B block)', fontsize=14)
    ax2.legend(loc='best')
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(data_min, data_max)
    ax2.set_xticks(ASSOCIATIVITIES)
    ax2.set_xticklabels([str(a) for a in ASSOCIATIVITIES])
    
    plt.tight_layout()
    plt.savefig('../../pics/exp2_3_associativity.png', dpi=150, bbox_inches='tight')
    print(f"\n图表已保存")
    print("\n相联度影响分析")
    for trace in TRACES:
        data = results[trace]
        if data['inst_rates'] and data['data_rates']:
            inst_improve = data['inst_rates'][-1] - data['inst_rates'][0]
            data_improve = data['data_rates'][-1] - data['data_rates'][0]
            print(f"{trace}:")
            print(f"  指令命中率提升 (1->64): {inst_improve:.4f}")
            print(f"  数据命中率提升 (1->64): {data_improve:.4f}")

if __name__ == "__main__":
    main()
