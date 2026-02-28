#!/usr/bin/env python3
import subprocess
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.join(BASE_DIR, "attachment", "code")
TRACES_DIR = os.path.join(BASE_DIR, "attachment", "traces")
SIM_PATH = os.path.join(CODE_DIR, "sim.exe")

def run_test(args, trace_file, test_name):
    trace_path = os.path.join(TRACES_DIR, trace_file)
    cmd = [SIM_PATH] + args + [trace_path]
    
    print(f"\n{'='*60}")
    print(f"测试: {test_name}")
    print(f"命令: {' '.join(cmd)}")
    print('='*60)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=CODE_DIR)
        print(result.stdout)
        if result.stderr:
            print("Errors:", result.stderr)
        return result.stdout
    except Exception as e:
        print(f"Error running test: {e}")
        return None

def main():
    # 检查模拟器是否存在
    if not os.path.exists(SIM_PATH):
        print(f"Error: 找不到模拟器 {SIM_PATH}")
        print("请先编译: cd attachment/code && make")
        return
    
    print("="*60)
    print("缓存模拟器测试")
    print("="*60)
    
    # 基本测试 - 使用默认配置
    base_args = ["-bs", "16", "-us", "8192", "-a", "1", "-wb", "-wa"]
    
    # 运行公开测试
    tests = [
        ("spice10.trace", "Spice10 - 10次访问"),
        ("spice100.trace", "Spice100 - 100次访问"),
        ("spice1000.trace", "Spice1000 - 1000次访问"),
        ("public-block.trace", "Public Block - 块大小"),
        ("public-assoc.trace", "Public Assoc - 关联度"),
        ("public-write.trace", "Public Write - 写策略"),
        ("public-instr.trace", "Public Instr - 指令缓存"),
    ]
    
    results = {}
    for trace, name in tests:
        output = run_test(base_args, trace, name)
        results[trace] = output
    
    # 不同块大小
    print("\n\n" + "="*60)
    print("不同块大小")
    print("="*60)
    
    for block_size in [8, 16, 32, 64]:
        args = ["-bs", str(block_size), "-us", "8192", "-a", "1", "-wb", "-wa"]
        run_test(args, "spice100.trace", f"块大小={block_size}")
    
    # 不同关联度
    print("\n\n" + "="*60)
    print("不同关联度")
    print("="*60)
    
    for assoc in [1, 2, 4, 8]:
        args = ["-bs", "16", "-us", "8192", "-a", str(assoc), "-wb", "-wa"]
        run_test(args, "spice100.trace", f"关联度={assoc}")
    
    # 写策略
    print("\n\n" + "="*60)
    print("写策略")
    print("="*60)
    
    # Write-back + Write-allocate
    run_test(["-bs", "16", "-us", "8192", "-a", "1", "-wb", "-wa"], 
             "spice100.trace", "写回+写分配")
    
    # Write-through + No-write-allocate
    run_test(["-bs", "16", "-us", "8192", "-a", "1", "-wt", "-nw"], 
             "spice100.trace", "写直通+非写分配")
    
    # 分离缓存测试
    print("\n\n" + "="*60)
    print("分离I/D缓存")
    print("="*60)
    
    run_test(["-bs", "16", "-is", "4096", "-ds", "4096", "-a", "1", "-wb", "-wa"],
             "spice100.trace", "分离缓存 I=4KB D=4KB")
    
    print("\n\n" + "="*60)
    print("所有测试完成")
    print("="*60)

if __name__ == "__main__":
    main()
