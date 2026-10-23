# TSP Memetic Algorithm 小组作业

本项目复现 Merz 与 Freisleben 关于 TSP 的 Memetic Algorithm 思路，并比较交叉算子与局部搜索的配合。

- [项目说明](项目说明.md)：问题背景、术语、算法和实验结论。
- [最终展示 PPT](算法PPT_最终版.pptx)：已完成的课堂汇报。
- [代码与复现](tsp_memetic/README.md)：环境安装、测试、实验参数与结果来源。
- `reference/`：参考论文。

快速检查：进入 `tsp_memetic`，执行 `python -m pip install -r requirements-dev.txt`、`python -m pytest -p no:cacheprovider tests`。仅重画汇报实验图可执行 `python experiments/plot_final_results.py`。
