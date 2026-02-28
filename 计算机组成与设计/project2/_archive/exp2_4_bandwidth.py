#!/usr/bin/env python3
import subprocess
import re
import os

SIM_PATH = "./sim"
TRACES_DIR = "../ext_traces"
TRACES = ["spice.trace", "cc.trace", "tex.trace"]
CONFIGS = [
    {"cache_size": 8192, "block_size": 64, "assoc": 2},
    {"cache_size": 8192, "block_size": 128, "assoc": 4},
    {"cache_size": 16384, "block_size": 64, "assoc": 4},
    {"cache_size": 16384, "block_size": 128, "assoc": 2},
    {"cache_size": 8192, "block_size": 64, "assoc": 4},
]

def run_sim(cache_size, block_size, assoc, writeback, writealloc, trace_file):
    cmd = [
        SIM_PATH,
        "-bs", str(block_size),
        "-is", str(cache_size),
        "-ds", str(cache_size),
        "-a", str(assoc),
    ]
    
    if writeback:
        cmd.append("-wb")
    else:
        cmd.append("-wt")
    
    if writealloc:
        cmd.append("-wa")
    else:
        cmd.append("-nw")
    
    cmd.append(os.path.join(TRACES_DIR, trace_file))
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        output = result.stdout
        demand_fetch = 0
        copies_back = 0
        lines = output.split('\n')
        for line in lines:
            if 'demand fetch' in line:
                match = re.search(r'demand fetch:\s+(\d+)', line)
                if match:
                    demand_fetch = int(match.group(1))
            elif 'copies back' in line:
                match = re.search(r'copies back:\s+(\d+)', line)
                if match:
                    copies_back = int(match.group(1))
        
        total_traffic = demand_fetch + copies_back
        return demand_fetch, copies_back, total_traffic
    except Exception as e:
        print(f"Error running sim: {e}")
        return None, None, None

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    code_dir = os.path.join(script_dir, "attachment", "code")
    os.chdir(code_dir)
    print(f"Working directory: {os.getcwd()}")
    
    # 实验A: WT vs WB (固定 WNA)
    print("\n" + "="*80)
    print("实验A: WT vs WB (固定WNA)")
    print("="*80)
    
    results_a = []
    for trace in TRACES:
        print(f"\n{trace}:")
        print(f"{'Config':<25} {'WT Traffic':>12} {'WB Traffic':>12} {'Diff':>10}")
        print("-" * 60)
        
        for cfg in CONFIGS:
            # Write-Through + WNA
            _, _, wt_traffic = run_sim(
                cfg['cache_size'], cfg['block_size'], cfg['assoc'],
                writeback=False, writealloc=False, trace_file=trace
            )
            
            # Write-Back + WNA
            _, _, wb_traffic = run_sim(
                cfg['cache_size'], cfg['block_size'], cfg['assoc'],
                writeback=True, writealloc=False, trace_file=trace
            )
            
            if wt_traffic and wb_traffic:
                diff = wt_traffic - wb_traffic
                diff_pct = (diff / wb_traffic * 100) if wb_traffic > 0 else 0
                cfg_str = f"{cfg['cache_size']//1024}K/{cfg['block_size']}B/{cfg['assoc']}way"
                print(f"{cfg_str:<25} {wt_traffic:>12} {wb_traffic:>12} {diff:>+10} ({diff_pct:+.1f}%)")
                results_a.append({
                    'trace': trace, 'config': cfg_str,
                    'wt': wt_traffic, 'wb': wb_traffic, 'diff': diff
                })
    
    # 实验B: WA vs WNA (固定 WB)
    print("\n" + "="*80)
    print("实验B: WA vs WNA (固定WB)")
    print("="*80)
    
    results_b = []
    for trace in TRACES:
        print(f"\n{trace}:")
        print(f"{'Config':<25} {'WA Traffic':>12} {'WNA Traffic':>12} {'Diff':>10}")
        print("-" * 60)
        
        for cfg in CONFIGS:
            # Write-Back + WA
            _, _, wa_traffic = run_sim(
                cfg['cache_size'], cfg['block_size'], cfg['assoc'],
                writeback=True, writealloc=True, trace_file=trace
            )
            
            # Write-Back + WNA
            _, _, wna_traffic = run_sim(
                cfg['cache_size'], cfg['block_size'], cfg['assoc'],
                writeback=True, writealloc=False, trace_file=trace
            )
            
            if wa_traffic and wna_traffic:
                diff = wa_traffic - wna_traffic
                diff_pct = (diff / wna_traffic * 100) if wna_traffic > 0 else 0
                cfg_str = f"{cfg['cache_size']//1024}K/{cfg['block_size']}B/{cfg['assoc']}way"
                print(f"{cfg_str:<25} {wa_traffic:>12} {wna_traffic:>12} {diff:>+10} ({diff_pct:+.1f}%)")
                results_b.append({
                    'trace': trace, 'config': cfg_str,
                    'wa': wa_traffic, 'wna': wna_traffic, 'diff': diff
                })
    
    # 生成Typst表格代码
    print("\n" + "="*80)
    print("Typst表格代码（实验A）:")
    print("="*80)
    print("""#figure(
  table(
    columns: (auto, auto, auto, auto, auto),
    inset: 5pt,
    align: center,
    [Trace], [Config], [WT Traffic], [WB Traffic], [Winner],""")
    for r in results_a:
        winner = "WB" if r['wb'] < r['wt'] else "WT"
        print(f"    [{r['trace'].replace('.trace','')}], [{r['config']}], [{r['wt']}], [{r['wb']}], [{winner}],")
    print("""  ),
  caption: [实验A: Write-Through vs Write-Back (Write-No-Allocate)]
)""")
    
    print("\n" + "="*80)
    print("Typst表格代码（实验B）:")
    print("="*80)
    print("""#figure(
  table(
    columns: (auto, auto, auto, auto, auto),
    inset: 5pt,
    align: center,
    [Trace], [Config], [WA Traffic], [WNA Traffic], [Winner],""")
    for r in results_b:
        winner = "WA" if r['wa'] < r['wna'] else "WNA"
        print(f"    [{r['trace'].replace('.trace','')}], [{r['config']}], [{r['wa']}], [{r['wna']}], [{winner}],")
    print("""  ),
  caption: [实验B: Write-Allocate vs Write-No-Allocate (Write-Back)]
)""")

if __name__ == "__main__":
    main()
