### 项目概览：Cache 模拟器与性能评估

**核心目标：**

1. 编写一个 Cache 模拟器并验证其正确性 。


2. 使用该模拟器对不同的 Cache 组织方式和管理策略进行性能评估研究 。



---

### 第一部分：构建 Cache 模拟器

你需要编写一个“迹驱动（Trace-driven）”模拟器，它读取内存访问记录（Trace）并模拟 Cache 的行为 。

#### 1. 模拟器功能要求

你的模拟器必须支持通过命令行参数配置以下参数 ：

* 
**总 Cache 大小** (Total cache size) 


* 
**块大小** (Block size) 


* 
**结构类型**：统一 Cache (Unified) vs. 独立指令/数据 Cache (Split I- and D-caches) 


* 
**相联度** (Associativity) 


* 
**写策略**：写回 (Write back, WB) vs. 写直达 (Write through, WT) 


* 
**分配策略**：写分配 (Write allocate, WA) vs. 写不分配 (Write no allocate, WNA) 



**注意**：所有大小参数（块大小、Cache 大小）单位均为**字节 (Bytes)** 。

#### 2. 统计数据要求

模拟器必须收集并报告以下数据，用于验证和评估 ：

* 指令引用次数 (Instruction references) 


* 数据引用次数 (Data references) 


* 指令缺失次数 (Instruction misses) 


* 数据缺失次数 (Data misses) 


* 从内存读取的字数 (Words fetched from memory) 


* 写回内存的字数 (Words copied back to memory) 



#### 3. 文件说明

项目包含以下文件 ：

* 
**Makefile**：用于编译，生成名为 `sim` 的可执行文件 。


* 
**main.c**：主程序驱动。包含参数解析 (`parse_args`) 和读取 Trace 的循环 (`play_trace`)。**尽量不要修改此文件** 。


* 
**cache.c**：Cache 模型核心代码。你需要在此实现主要逻辑 。


* 已提供：`set_cache_param` (设置参数), `delete`/`insert` (双向链表操作), `dump_settings`/`print_stats` (打印结果) 。


* **你需要编写**：
1. 
`init_cache()`: 初始化数据结构 。


2. 
`perform_access()`: 模拟单次内存访问 。


3. 
`flush()`: 模拟结束时清空 Cache（处理脏块） 。






* 
**cache.h**：头文件，包含 `cache` 和 `cache_line` 结构体定义 。


* 
**Trace 文件** (`spice.trace`, `cc.trace`, `tex.trace`)：用于测试的内存访问记录 。



#### 4. Trace 文件格式

Trace 文件为 ASCII 格式，每行代表一次内存访问，包含两个数字 ：

1. 
**引用类型** (0-2) ：


* 
`0`: 数据读取 (Data load) 


* 
`1`: 数据写入 (Data store) 


* 
`2`: 指令读取 (Instruction load) 




2. 
**内存地址**：十六进制格式的 32 位字节地址 。



#### 5. 实施建议 (逐步构建)

建议按以下顺序开发，每一步都需测试 ：

1. 先实现：统一 Cache、固定块大小、直接映射 (Direct-mapped)、写回 (WB)、写分配 (WA) 。


2. 增加变量块大小功能 。


3. 增加相联度 (Associativity) 支持 。


4. 增加分离式 (Split) Cache 支持 。


5. 增加写直达 (WT) 支持 。


6. 增加写不分配 (WNA) 支持 。



**技术提示**：

* 利用提供的双向链表结构实现 LRU（最近最少使用）替换策略 。


* 访问时，将命中的行移至链表头部；需要替换时，移除链表尾部的行 。



#### 6. 验证 (Validation)

在进行第二部分之前，必须使用 `spice.trace` 运行你的模拟器，并将输出结果与文档中的 **Table 1** (第 7 页) 进行比对 。所有统计数据必须完全一致 。

---

### 第二部分：性能评估实验

使用你通过验证的模拟器，对三个 Trace 文件（spice, gcc, TeX）进行以下实验。

#### 实验 2.1：工作集特征 (Working Set Characterization)

* 
**目的**：确定程序的指令和数据工作集大小 。


* **设置**：
* 结构：分离式 Cache (Split I/D) 。


* 相联度：**全相联** (Fully associative) 以消除冲突缺失 。


* 块大小：始终为 **4 字节** 。


* 策略：写回 (WB)，写分配 (WA) 。


* 变量：Cache 大小。从 4 字节开始，每次增加 2 倍，直到命中率不再变化 。




* **任务**：
1. 绘制“命中率 (Hit Rate) vs. Cache 大小”的曲线图（每个 Trace 画两张：指令和数据各一张）。


2. 回答问题：
* 解释实验原理及图中特征的含义 。


* 三个 Trace 的指令工作集和数据工作集大小各是多少？







#### 实验 2.2：块大小的影响 (Impact of Block Size)

* **设置**：
* 结构：分离式 Cache，I-Cache 和 D-Cache 各 **8 KB** 。


* 相联度：**2 路** 。


* 策略：写回 (WB)，写分配 (WA) 。


* 变量：块大小。从 4 字节到 4 KB，按 2 的幂次变化 。




* **任务**：
1. 绘制“命中率 vs. 块大小”的曲线图（每个 Trace 分指令和数据）。


2. 回答问题：
* 解释曲线形状的原因，特别是**空间局部性 (Spatial Locality)** 的影响 。


* 每个 Trace 的最佳块大小是多少？


* 指令和数据的最佳块大小是否不同？这说明了什么？







#### 实验 2.3：相联度的影响 (Impact of Associativity)

* **设置**：
* 结构：分离式 Cache，I-Cache 和 D-Cache 各 **8 KB** 。


* 块大小：**128 字节** 。


* 策略：写回 (WB)，写分配 (WA) 。


* 变量：相联度。从 1 到 64，按 2 的幂次变化 。




* **任务**：
1. 绘制“命中率 vs. 相联度”的曲线图（每个 Trace 分指令和数据）。


2. 回答问题：
* 解释曲线形状的原因 。


* 指令和数据的表现有何不同？说明了相联度对两者的影响有何差异？







#### 实验 2.4：内存带宽 (Memory Bandwidth)

* **实验 A：写策略对比 (WT vs. WB)**
* 设置：分离式 Cache，写不分配 (Write-No-Allocate)。
* 测试参数：选择几组合理的大小（如 8KB/16KB）、块大小（如 64/128B）、相联度（2/4）。总共跑 4-5 次模拟 。


* 比较：写直达 (Write-Through) 与 写回 (Write-Back) 的总内存流量 。


* 
**回答**：哪个产生的流量更小？为什么？是否有反转的情况？




* **实验 B：分配策略对比 (WA vs. WNA)**
* 设置：同上，但固定为 **写回 (Write-Back)** 策略 。


* 比较：写分配 (Write-Allocate) 与 写不分配 (Write-No-Allocate) 。


* 
**回答**：哪个产生的流量更小？为什么？是否有反转的情况？