#!/usr/bin/env python3
import subprocess
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.join(BASE_DIR, "attachment", "code")
TRACES_DIR = os.path.join(BASE_DIR, "attachment", "ext_traces")
SIM_PATH = os.path.join(CODE_DIR, "sim.exe")

TABLE1_DATA = [
    # CS,     Type,     BS,  Ass, Write, Alloc, I_Miss, I_Repl, D_Miss, D_Repl, DF,     CB
    ("8K",   "Split",   16,   1, "WB",  "WA",  24681,  24173,   8283,   7818, 131856,  12024),
    ("16K",  "Split",   16,   1, "WB",  "WA",  11514,  10560,   5839,   5051,  69412,   8008),
    ("32K",  "Split",   16,   1, "WB",  "WA",   5922,   4321,   1567,    520,  29956,   3628),
    ("64K",  "Split",   16,   1, "WB",  "WA",   2619,    484,   1290,    103,  15636,   3324),
    ("8K",   "Unified", 16,   1, "WB",  "WA",  36136,  35787,  21261,  21098, 229588,  37844),
    ("8K",   "Unified", 32,   1, "WB",  "WA",  26673,  26502,  19561,  19476, 369872,  69104),
    ("8K",   "Unified", 64,   1, "WB",  "WA",  23104,  23029,  20377,  20324, 695696, 136112),
    ("32K",  "Split",  128,   1, "WB",  "WA",   1964,   1726,    459,    280,  77536,   7296),
    ("8K",   "Split",   64,   2, "WB",  "WA",   6590,   6462,   3160,   3032, 156000,  18880),
    ("8K",   "Split",   64,   4, "WB",  "WA",   6025,   5897,    875,    747, 110400,   7296),
    ("8K",   "Split",   64,   8, "WB",  "WA",   6435,   6307,    803,    675, 115808,   6656),
    ("8K",   "Split",   64,  16, "WB",  "WA",   6536,   6408,    799,    671, 117360,   6624),
    ("8K",   "Split",   64, 128, "WB",  "WA",   6523,   6395,    790,    662, 117008,   6576),
    ("1K",   "Split",   64,   2, "WB",  "WA",  44962,  44946,  24767,  24751,1115664, 149200),
    ("1K",   "Split",   64,   8, "WB",  "WA",  45885,  45869,  22808,  22792,1099088, 112480),
    ("1K",   "Split",   64,  16, "WB",  "WA",  45969,  45953,  20667,  20651,1066176,  90416),
    ("8K",   "Split",   16,   1, "WT",  "WA",  24681,  24173,   8283,   7818, 131856,  66538),
    ("8K",   "Split",   32,   1, "WT",  "WA",  15868,  15612,   7504,   7264, 186976,  66538),
    ("8K",   "Split",   64,   2, "WT",  "WA",   6590,   6462,   3160,   3032, 156000,  66538),
    ("8K",   "Split",   16,   1, "WB", "WNA",  24681,  24173,  14904,   6688, 127304,  14643),
    ("8K",   "Split",   32,   1, "WB", "WNA",  15868,  15612,  15098,   6421, 180200,  22033),
    ("8K",   "Split",   64,   2, "WB", "WNA",   6590,   6462,   8638,   2726, 151104,  13624),
]

def parse_size(s):
    s = s.strip().upper()
    if s.endswith('K'):
        return int(s[:-1]) * 1024
    return int(s)

def run_sim(cache_size, cache_type, block_size, assoc, write_policy, alloc_policy, trace_file):
    args = [SIM_PATH]
    args.extend(["-bs", str(block_size)])
    
    size = parse_size(cache_size)
    if cache_type == "Unified":
        args.extend(["-us", str(size)])
    else:  # Split
        args.extend(["-is", str(size), "-ds", str(size)])
    
    args.extend(["-a", str(assoc)])
    
    if write_policy == "WB":
        args.append("-wb")
    else:  # WT
        args.append("-wt")
    
    if alloc_policy == "WA":
        args.append("-wa")
    else:  # WNA
        args.append("-nw")
    
    args.append(os.path.join(TRACES_DIR, trace_file))
    
    try:
        result = subprocess.run(args, capture_output=True, text=True, cwd=CODE_DIR)
        output = result.stdout
        stats = {}
        inst_match = re.search(r'INSTRUCTIONS\s+accesses:\s+\d+\s+misses:\s+(\d+).*?replace:\s+(\d+)', output, re.DOTALL)
        if inst_match:
            stats['i_miss'] = int(inst_match.group(1))
            stats['i_repl'] = int(inst_match.group(2))
        data_match = re.search(r'DATA\s+accesses:\s+\d+\s+misses:\s+(\d+).*?replace:\s+(\d+)', output, re.DOTALL)
        if data_match:
            stats['d_miss'] = int(data_match.group(1))
            stats['d_repl'] = int(data_match.group(2))
        df_match = re.search(r'demand fetch:\s+(\d+)', output)
        cb_match = re.search(r'copies back:\s+(\d+)', output)
        if df_match:
            stats['df'] = int(df_match.group(1))
        if cb_match:
            stats['cb'] = int(cb_match.group(1))
        
        return stats
    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    if not os.path.exists(SIM_PATH):
        print(f"Error: 找不到模拟器 {SIM_PATH}")
        return
    
    print("=" * 120)
    print("Cache Simulator Validation - Table 1 (spice.trace)")
    print("=" * 120)
    
    # 表头
    header = f"{'CS':>5} {'Type':>8} {'BS':>4} {'Ass':>4} {'Wr':>3} {'Al':>4} | " \
             f"{'I_Miss':>7} {'I_Repl':>7} {'D_Miss':>7} {'D_Repl':>7} {'DF':>8} {'CB':>8} | {'Status':>8}"
    print(header)
    print("-" * 120)
    
    passed = 0
    failed = 0
    
    for row in TABLE1_DATA:
        cs, ctype, bs, ass, wr, al, exp_im, exp_ir, exp_dm, exp_dr, exp_df, exp_cb = row
        
        stats = run_sim(cs, ctype, bs, ass, wr, al, "spice.trace")
        
        if stats:
            im = stats.get('i_miss', -1)
            ir = stats.get('i_repl', -1)
            dm = stats.get('d_miss', -1)
            dr = stats.get('d_repl', -1)
            df = stats.get('df', -1)
            cb = stats.get('cb', -1)
            
            # 检查是否匹配
            match = (im == exp_im and ir == exp_ir and dm == exp_dm and 
                     dr == exp_dr and df == exp_df and cb == exp_cb)
            
            status = "PASS" if match else "FAIL"
            if match:
                passed += 1
            else:
                failed += 1
            
            print(f"{cs:>5} {ctype:>8} {bs:>4} {ass:>4} {wr:>3} {al:>4} | "
                  f"{im:>7} {ir:>7} {dm:>7} {dr:>7} {df:>8} {cb:>8} | {status:>8}")
            
            if not match:
                print(f"      Expected: {exp_im:>7} {exp_ir:>7} {exp_dm:>7} {exp_dr:>7} {exp_df:>8} {exp_cb:>8}")
        else:
            failed += 1
            print(f"{cs:>5} {ctype:>8} {bs:>4} {ass:>4} {wr:>3} {al:>4} | {'ERROR':>60}")
    
    print("-" * 120)
    print(f"Results: {passed} passed, {failed} failed out of {len(TABLE1_DATA)} tests")
    print("=" * 120)

if __name__ == "__main__":
    main()
