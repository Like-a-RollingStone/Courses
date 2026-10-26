# 线性拟合实验

基于 MindSpore 2.2.0 的线性函数拟合课程实验，包含基础线性回归、噪声强度对比，以及一层隐藏层 MLP 的训练与对比分析。

## 归档状态

已建立实验目录。以下是待上传的本地成果清单，本 README 的创建不代表这些文件已经上传。

| 文件 | 用途 |
| --- | --- |
| 基于MindSpore的线性回归模拟实验.ipynb | 实验代码、训练日志、预测和内嵌图像，包含 baseline、噪声 5/20/50、MLP 对比 |
| Report.typ | 实验报告 Typst 源文件 |
| Report.pdf | 可直接阅读的实验报告 |
| baseline_linear_fit.png | 基础线性拟合结果 |
| noise_scale_comparison.png | 不同噪声强度对比 |
| mlp_structure_comparison.png | 线性模型与优化后 MLP 的对比 |

上述六个文件计划与本 README 放在同一级目录，以保持报告中的图片相对路径有效。

## 环境与阅读说明

- 本地实验环境为 Windows、Python 3.9.25、MindSpore 2.2.0、CPU，Notebook 内核为 Python(ms_exp)。
- 主要运行依赖为 numpy、mindspore、Pillow 和 Jupyter/ipykernel。
- 线性模型使用 Dense(1, 1)、SGD、20 个 epoch。
- 优化后 MLP 使用 1-8-ReLU-1、Adam(lr=0.01)、500 个 epoch。
- Notebook 中 final_loss 是最后一个训练样本/批次的更新前损失，不等于全训练集 MSE；结构对比另行输出 train_mse。
- 结构对比同时改变了优化器和训练轮数，结果反映各自训练设置下的表现，不能单独归因于网络结构。
- Report.typ 依赖本地模板 @local/tplt:0.3.0，以及文件中指定的 Typst preview 包。模板尚未归档，其他机器暂不能仅靠本目录保证重新编译；可先阅读 Report.pdf。
- 模拟数据由 Notebook 固定种子生成，不需要单独上传数据集。

## 不纳入本次上传

- 教师提供的实验指导书 .docx：作为课程参考资料，暂不公开再分发。
- prompt.md：本地环境交接说明；归档所需说明集中在本 README。
- 环境目录、缓存、临时调参脚本和密钥：不属于实验成果。

本地文件已核对；上传前应以文件的最新版本为准。
