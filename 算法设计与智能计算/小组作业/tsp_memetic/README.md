# TSP Memetic Algorithm 代码与复现

本目录是《算法设计与智能计算》小组作业的代码提交版，对应上一级的 `算法PPT_最终版.pptx` 和 `项目说明.md`。实现保留汇报时的算法与实验设置，结果来自已保存的多次随机运行。

## 环境与快速检查

使用 Python 3.10 或更新版本，在本目录执行：

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -p no:cacheprovider tests
python experiments/run_conclusion_exploration.py --mode smoke --workers 1
```

`requirements.txt` 是算法和绘图依赖；`requirements-dev.txt` 额外安装 pytest。NumPy 需至少为 2.0，因为实验脚本使用 `numpy.trapezoid` 计算 gap 曲线面积。无图形桌面的 Linux/WSL 可先设置 `MPLBACKEND=Agg`。

测试涉及精确算法基准、交叉后排列合法性、局部搜索不增大路径长度、固定边保护、GA/MA 回调等。smoke 只运行 3 个小任务，写出 `smoke_*.csv` 和烟雾测试图片，用于检查读取数据、求解和绘图流程。

## 目录

| 路径 | 内容 |
|---|---|
| `src/` | TSPLIB 读取、Tour、GA/MA、交叉算子、2-opt、Or-opt、有界 L-K |
| `data/tsplib/` | 实验与测试所需的 TSPLIB 数据和最优值索引 |
| `experiments/` | 主实验、扩展实验、早期消融实验与结果绘图入口 |
| `tests/` | 原项目的正确性测试 |
| `results/paper_tables/` | 主实验原始记录、汇总、参数和边结构分析表 |
| `results/conclusion_exploration/` | L-K 强度、种群、多 seed、多地图的记录与汇总 |
| `results/ablation_tables/` | 早期消融实验结果，供补充查阅 |
| `report/figures/` | 最终汇报图及相关分析图 |

提交版不包含未使用的 Web 应用、依赖安装目录、Python 缓存、临时参数搜索及旧版图片快照。算法源码与原项目相同；PPT 代码截图是说明材料，执行时以 `src/` 为准。

## 不重跑算法，直接检查汇报图

```bash
python experiments/plot_final_results.py
```

该命令从提交的 CSV 重新生成第 10–14 页对应的 6 张实验图，写入 `report/figures/reproduced/`，便于追溯数据。原汇报图片保留在原目录；重画图的字体或排版可能随环境略有变化。

| PPT 页 | 数据来源 | 汇报图 |
|---|---|---|
| 10 | `results/paper_tables/large_instance_pilot_raw.csv` | `6_3_large_instance_pilot.png` |
| 11 | `results/paper_tables/large_instance_pilot_summary.csv` | `6_4_large_instance_pilot_summary.png` |
| 12 | `results/conclusion_exploration/multi_instance_gx_lk_summary.csv` | `conclusion_exploration/report_multi_instance_gx_lk_summary.png` |
| 13 | `results/conclusion_exploration/report_summary.csv` 的 `lk_strength_*` 组 | `conclusion_exploration/report_lk_strength.png` |
| 14 左 | 同表的 `population_*` 组 | `conclusion_exploration/report_population_size.png` |
| 14 右 | 同表的 `multi_seed` 组 | `conclusion_exploration/report_multiseed_robustness.png` |

表中图片路径相对于 `report/figures/`。CSV 的 gap 单位为百分比；图中的标准差误差条反映跨 seed 波动，不是置信区间。

## 重新运行正式实验

以下命令会更新对应的 CSV 和图片。建议先保留原结果副本，或在另一个项目副本中运行；完整实验明显慢于 smoke。

### d493 主实验，第 10–11 页

```bash
python experiments/run_large_instance_pilot.py --instances d493 --runs 10 --generations 8 --pop-size 6 --ls-step-budget 100000 --lk-warm-start-max-improvements 100000 --lk-max-improvements 12 --lk-max-depth 3 --lk-candidate-k 20 --lk-backtracking-width 1 --workers 4
```

参数来自 `results/paper_tables/large_instance_pilot_metadata.csv`。基础 seed 为 `20260617`，每个方法运行 10 次；交叉概率 0.9、变异概率 0.2。程序同时输出运行时间分析。`--workers` 可调低以减少 CPU 占用，测得的时间会受硬件和并行度影响。

### L-K 强度、种群、多 seed，第 13–14 页

```bash
python experiments/run_conclusion_exploration.py --mode report --base-seed 20260619 --workers 4
```

该命令运行 132 个任务，主体为 `ch130`，并引用已有 d493 汇总完成规模对照。各组分别使用独立的 seed 范围，详细 seed 保存在 `report_raw.csv`，不同参数组不应当作逐 seed 配对实验。

| 组别 | runs | generations | pop_size |
|---|---:|---:|---:|
| 早期双实例规模对照中的 ch130 | 5 | 6 | 6 |
| L-K 每档、每个方法 | 4 | 6 | 6 |
| 每个种群规模、每个方法 | 4 | 6 | 6 或 12 |
| 多 seed、每个方法 | 8 | 8 | 8 |

L-K 的 `(2-opt 预热改进上限, L-K 改进上限, 深度, 近邻数, 分支宽度)` 分别是：weak `(20, 1, 2, 8, 1)`，medium `(60, 3, 3, 12, 2)`，strong `(None, 5, 3, 15, 3)`。`None` 表示预热不设改进次数上限。这里的上限计数是接受的改进次数，不是时间或检查候选的次数。L-K 组使用 `full` 策略，仍受各自 L-K 参数约束；2-opt 种群和多 seed 对照使用 60 次改进上限。

### 多地图验证，第 12 页

```bash
python experiments/run_multi_instance_gx_lk_summary.py --instances eil51 eil101 ch130 --runs 8 --generations 8 --pop-size 8 --two-opt-budget 60 --workers 4
```

基础 seed 为 `20260621`。三个小中实例使用 medium L-K，d493 行引用主实验 CSV，因此应先准备好主实验结果。该脚本在不同方法间使用不同 seed 范围。四个地图内的各方法参数相同，但 d493 与三个小中实例的种群和局部搜索预算不同，不能把地图间的差异全归因于城市数。

### 其他分析

`run_paper_visualizations.py` 提供边结构、局部搜索前后、收敛、多样性等分析；`run_ablation.py`、`run_compare.py` 保留早期对照实验。它们各有独立的默认设置，不能以默认结果替代最终 PPT 的实验组。

## 实现和结果的解释范围

最终汇报的 `local_search="lk"` 使用 2-opt 预热加有界变深度 L-K；保留的 `lk-style` 是早期 2-opt + Or-opt 代理，二者不同。本项目没有实现完整 LKH，也没有复现原论文全部工程优化。

已知最优长度是 gap 的评价基准，启发式算法本身不提供全局最优证明。多地图结果中 GX + L-K 在 eil101、d493 均值第一，在 eil51、ch130 第二；这支持本实验条件下质量表现较稳定的结论。多 seed 的 ch130 组中 GX + L-K 均值最好，PMX + L-K 标准差最小；不能把“均值最好”写成“波动最小”。

DPX 波动和种群扩大后 GX + 2-opt 变差的解释是结合算子机制提出的假设。种群实验每组仅 4 次，且固定代数并不意味着固定计算量；更强 L-K 也未呈现质量或时间单调变化。以上现象需要更多 seed 和控制变量实验才能判断普遍性。
