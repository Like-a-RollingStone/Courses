#import "@local/tplt:0.3.0": *
#show: BL

#let course = [算法设计与智能计算]
#let teacher = [李旻]
#let proj = [基于MindSpore的线性函数拟合]
#let proj-short = [基于MindSpore的线性函数拟合实验]

#zju-cover(
  course: course,
  proj-name: [基于MindSpore的线性函数拟合],
  teacher: teacher,
)


#import "@preview/itemize:0.2.0" as el  
#show: el.default-enum-list 

#import "@preview/codelst:2.0.2":sourcecode

#set math.equation(numbering: "(30.1)")
#show math.equation.where(block: true): it => {
  if it.has("label") {
    if "-" == str(it.label) {
      counter(math.equation).update(n => n - 1)
      math.equation(it.body, block: true, numbering: none)
      return
    } else if "::" in str(it.label) {
      let (a, b) = str(it.label).split("::")
      counter(math.equation).update(n => n - 2)
      [#math.equation(it.body, block: true, numbering: _ => "(" + b + ")")#label(a)]
      return
    }
  }
  it
}

#show: RP.with(
  course: course,
  proj-name: proj-short,
)

/*
#exp-info-chart(
  course: course,
  exp-cate: [设计实验],
  teacher: teacher,

  exp-name: proj,
  where: [ ],
)
*/
#import "@preview/numbly:0.1.0": numbly
/*
#set heading(numbering: numbly(
  "{1}    ",
  "{1}.{2} ",
  "{1}.{2}.{3} ",
))
*/
#set par(first-line-indent: (amount: 2em, all: true))

#set enum(indent:2em)
#set list(indent:2em)

#set math.cases(gap: 0.7em)

#outline()

#pagebreak()
//正文从这里开始
= 实验环境

本实验按照《基于MindSpore的线性函数拟合实验》指导书完成，目标是在模拟数据上使用 MindSpore 构建并训练线性回归模型，观察模型对线性函数的拟合效果，并进一步分析数据噪声和网络结构变化对拟合结果的影响。

指导书默认环境为华为云ModelArts与Ascend算力，故原始示例代码中使用 `device_target="Ascend"`，即使用云平台算力。但由于发现云端资源始终无法创建，只能改用本地 Windows + Anaconda + MindSpore CPU 环境完成。指导书说明本案例支持 win_x86 和 Linux，CPU/GPU/Ascend 均可运行，因此该替代方案不会改变实验算法流程。实际配置运行环境如下：

- Python 内核：新建环境`Python(ms_exp)`，版本`3.9.25`  
- MindSpore 版本：`2.2.0`
- 运行设备：CPU
- 主要依赖：`numpy`、`mindspore`、`Pillow`

实验开始时在 Notebook 中执行环境检查：

#sourcecode[
```python
import mindspore as ms

print("MindSpore version:", ms.__version__)
ms.run_check()
```
]

输出显示 MindSpore 已在 CPU 平台安装成功，说明实验环境可以正常运行。

= 实验原理

线性回归假设预测值可以表示为输入特征的线性变换：

$ hat(y) = w x + b $

其中，$w$ 为权重，$b$ 为偏置。给定模拟数据后，训练目标是寻找合适的 $w$ 和 $b$，使模型预测值尽可能接近真实标签。本实验使用均方误差作为损失函数：

$ "MSE" = frac(1, n) sum_(i=1)^n (hat(y)_i - y_i)^2 $

优化器采用随机梯度下降 SGD。模型训练过程中，MindSpore 根据前向计算得到损失，再通过自动微分计算梯度并更新参数。

= 实验过程

== 数据生成

实验数据由一维自变量 $x$ 和标签 $y$ 构成。自变量在区间 $[-5, 5)$ 内按步长 0.3 生成，并截取 32 个样本。标签按照线性函数加入随机扰动：

$ y = -5 x + 0.1 times "noise" $

其中，`noise` 服从均值为 0 的正态分布。baseline 实验使用指导书原始设置 `noise_scale=20`。为了保证结果可复现，实验中固定随机种子：

#sourcecode[
```python
np.random.seed(42)
ms.set_seed(42)
```
]

== 模型构建与训练

baseline 模型使用指导书中的简单线性结构：

#sourcecode[
```python
net = nn.Dense(1, 1)
loss_fn = nn.MSELoss()
opt = nn.SGD(net.trainable_params(), learning_rate=0.01)
```
]

训练过程共进行 20 个 epoch。每个 epoch 遍历 32 个样本，计算 MSE 损失并用 SGD 更新参数。训练结束后，baseline 的最终训练损失为 1.493384。

== 模型预测与可视化

训练完成后读取模型的可训练参数，并在 $x=-10,-5,0,5,10$ 等关键点上进行预测。Notebook 同时生成散点图、训练模型曲线和真实函数参考线，便于观察拟合效果。

#figure(
  image("baseline_linear_fit.png", width: 90%),
  caption: [baseline 线性拟合结果],
)

= 实验数据

== Baseline 参数与预测结果

baseline 训练后得到的线性模型为：

$ y = -5.052402 x + 0.339533 $

该模型的权重接近真实斜率 $-5$，说明简单线性模型已经成功学习到数据的主要线性趋势。关键预测结果如下表所示。

#table(
  columns: 2,
  inset: 6pt,
  align: center,
  [输入 $x$], [预测值],
  [`-10`], [`50.863556`],
  [`-5`], [`25.601545`],
  [`0`], [`0.339533`],
  [`5`], [`-24.922480`],
  [`10`], [`-50.184494`],
)

== 不同噪声强度对比

为了分析数据质量对拟合效果的影响，本实验在保持模型结构和训练参数不变的前提下，对比 `noise_scale=5`、`20`、`50` 三组数据。

其中 `20` 是指导书 baseline 设置。



#table(
  columns: 5,
  inset: 5pt,
  align: center,
  [噪声强度], [最终损失], [$w$], [$b$], [$w$ 误差],
  [`5`], [`0.093336`], [`-5.013101`], [`0.084885`], [`0.013101`],
  [`20`], [`1.493384`], [`-5.052402`], [`0.339533`], [`0.052402`],
  [`50`], [`9.333697`], [`-5.131005`], [`0.848828`], [`0.131005`],
)

#figure(
  image("noise_scale_comparison.png", width: 100%),
  caption: [不同噪声强度下的线性拟合结果],
)

== 不同网络结构对比

进一步在同一 baseline 数据集上比较简单线性模型与一层隐藏层 MLP，结构为：

#sourcecode[
```python
nn.SequentialCell([
    nn.Dense(1, 8),
    nn.ReLU(),
    nn.Dense(8, 1),
])
```
]

线性模型保留指导书的 SGD 与 20 个 epoch 设置。MLP 参数更多、训练更敏感，因此使用 Adam 优化器并增加到 500 个 epoch，使其充分学习负线性斜率。实验结果如下：

#table(
  columns: 6,
  inset: 5pt,
  align: center,
  [模型], [优化器], [epoch], [最终损失], [训练集 MSE], [`x=10` 预测],
  [Linear Dense(1,1)], [SGD], [`20`], [`1.493401`], [`2.952100`], [`-50.184494`],
  [MLP 1-8-ReLU-1], [Adam], [`500`], [`1.043528`], [`2.398825`], [`-46.121098`],
)

#figure(
  image("mlp_structure_comparison.png", width: 95%),
  caption: [线性模型与一层隐藏层 MLP 的拟合对比],
)

= 数据分析

== Baseline 拟合效果分析

baseline 模型学习到的权重为 `-5.052402`，与真实斜率 `-5` 的误差约为 `0.052402`。从预测结果看，当 $x$ 从负数增大到正数时，预测值呈稳定下降趋势，与真实函数 $y=-5x+0.1$ 的方向一致。可视化图中，训练模型曲线与真实函数参考线基本重合，说明 MindSpore 线性模型能够完成指导书要求的线性函数拟合任务。

== 噪声强度影响分析

三组噪声对比说明，噪声越小，样本点越集中在真实直线附近，最终损失和参数误差也越小。`noise_scale=5` 时，最终损失仅为 `0.093336`，斜率误差为 `0.013101`；当噪声增大到 `50` 时，最终损失上升到 `9.333697`，斜率误差增大到 `0.131005`。

这说明噪声会降低训练数据中线性关系的清晰程度，使模型更难准确估计参数。但即使在高噪声设置下，学习到的斜率仍为 `-5.131005`，整体仍接近真实斜率 `-5`，说明简单线性模型对主要线性趋势具有一定鲁棒性。

== 网络结构影响分析

MLP 结构具有更强表达能力，但也需要更充分的优化。初始尝试中若直接套用线性模型的 20 个 epoch 与 SGD 设置，MLP 容易训练不充分，无法得到负线性曲线，而是会拟合为常数。将 MLP 调整为 Adam 优化器并训练 500 个 epoch 后，其最终损失降至 `1.043528`，训练集 MSE 为 `2.398825`，并且在可视化图中学到了明显的负线性趋势。

不过，MLP 的 `x=10` 预测为 `-46.121098`，相比线性模型的 `-50.184494` 仍有一定差距。这说明复杂模型经过调参后可以完成拟合，但对于由线性函数生成的数据，简单线性模型的结构与数据规律更直接匹配，训练成本更低、解释性更强。该对比说明，模型选择不仅取决于表达能力，也取决于任务规律和训练设置是否匹配。

= 实验总结

本实验在本地 Windows CPU 环境下完成了指导书中的 MindSpore 线性函数拟合流程。除将原始代码的 `device_target="Ascend"` 改为 `device_target="CPU"`，其余数据生成、模型构建、损失函数、优化器、训练、预测和可视化流程均与指导书保持一致。

通过不同噪声强度对比可以看到，噪声越大，训练损失和参数误差越大，但模型仍能学习主要线性趋势；通过 MLP 结构对比可以看到，优化后的 MLP 也能学习负线性斜率，但需要 Adam 和更多训练轮次；对于线性数据，简单线性模型仍具有更好的稳定性和可解释性。

