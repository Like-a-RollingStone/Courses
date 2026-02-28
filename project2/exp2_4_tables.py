#!/usr/bin/env python3
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.family'] = ['SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

data_a = [
    ("spice", "8K/64B/2way", 217642, 164728, "WB"),
    ("spice", "16K/128B/4way", 130858, 73988, "WB"),
    ("cc", "8K/64B/2way", 557286, 513682, "WB"),
]

data_b = [
    ("spice", "8K/64B/2way", 174880, 164728, "NW"),
    ("spice", "16K/128B/4way", 73504, 73988, "WA"),
    ("cc", "8K/64B/2way", 530816, 513682, "NW"),
]

def create_table_image(data, columns, title, filename):
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.axis('tight')
    ax.axis('off')
    table_data = [list(row) for row in data]
    table = ax.table(
        cellText=table_data,
        colLabels=columns,
        cellLoc='center',
        loc='center',
        colColours=['#4472C4'] * len(columns)
    )
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 1.8)
    for i in range(len(columns)):
        table[(0, i)].set_text_props(color='white', fontweight='bold')
    for i, row in enumerate(data):
        winner_col = len(columns) - 1
        table[(i+1, winner_col)].set_facecolor('#90EE90')
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"已保存: {filename}")

def main():
    columns_a = ["Trace", "Config", "WT+NW", "WB+NW", "Winner"]
    create_table_image(data_a, columns_a,
        "实验A: Write-Through vs Write-Back (固定 Write-No-Allocate)",
        "pics/exp2_4_table_a.png")
    columns_b = ["Trace", "Config", "WB+WA", "WB+NW", "Winner"]
    create_table_image(data_b, columns_b,
        "实验B: Write-Allocate vs Write-No-Allocate (固定 Write-Back)",
        "pics/exp2_4_table_b.png")
    print("\n表格已生成")

if __name__ == "__main__":
    main()
