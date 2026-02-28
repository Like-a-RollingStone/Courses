#import "@local/tplt:0.3.0": *
#show: BL

#let course = [计算机组成与设计]
#let teacher = [赵武锋]
#let proj = [cache 仿真器与性能分析]
#let proj-short = [cache仿真器与性能分析]

#zju-cover(
  course: course,
  proj-name: [cache 仿真器与性能分析],
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

= 实验概述

本实验旨在实现一个跟踪驱动的缓存模拟器，用于评估不同缓存架构特性对性能的影响。模拟器通过读取内存访问跟踪文件，模拟数据在缓存中的进出行为，收集命中率、缺失率、内存流量等关键性能指标。实验过程中需要实现缓存初始化、访问处理和刷新三个核心功能，并验证模拟器在不同配置下的正确性。

= 任务一：缓存模拟器实现
高速缓存模拟器将可以根据命令行中给出的参数进行配置，并且必须支持以下功能：
- Total cache size
- Block size
- Unified vs. split I- and D-caches
- Associativity
- Write back vs. write through
- Write allocate vs. write no allocate

模拟器必须跟踪：
- Number of instruction references
- Number of data references
- Number of instruction misses
- Number of data misses
- Number of words fetched from memory
- Number of words copied back to memory
== 核心数据结构

缓存模拟器采用双向链表实现LRU替换策略。每个缓存行包含标签(tag)和脏位(dirty)字段，通过LRU_next和LRU_prev指针维护访问顺序。缓存结构体包含大小、关联度、组数、索引掩码等配置信息，以及指向每组LRU链表头尾的指针数组。统计结构体记录访问次数、缺失次数、替换次数、需求取回字数和写回字数。

#sourcecode[```c
typedef struct cache_line_ {
  unsigned tag;
  int dirty;
  struct cache_line_ *LRU_next;
  struct cache_line_ *LRU_prev;
} cache_line, *Pcache_line;

typedef struct cache_ {
  int size;               /* cache size */
  int associativity;      /* cache associativity */
  int n_sets;             /* number of cache sets */
  unsigned index_mask;    /* mask to find cache index */
  int index_mask_offset;  /* number of zero bits in mask */
  Pcache_line *LRU_head;  /* head of LRU list for each set */
  Pcache_line *LRU_tail;  /* tail of LRU list for each set */
  int *set_contents;      /* number of valid entries in set */
} cache, *Pcache;
```]

`cache_line`结构体表示单个缓存行。其中`tag`用于地址匹配，`dirty`标记该行是否被修改过（用于写回策略），双向链表指针用于LRU排序。`cache`结构体描述整个缓存的配置，`index_mask`和`index_mask_offset`用于从地址中快速提取组索引，`LRU_head`和`LRU_tail`数组分别指向每组的LRU链表头尾。

== cache初始化

先实现 cache 的初始化，命令行参数获取和设置代码框架已经给出，只需要在 cache.c中实现 init_cache 函数即可。

首先将指令和数据的统计计数器清零，然后根据cache_split标志判断是统一缓存还是分离缓存模式。对于统一缓存，仅初始化c1结构体并使icache和dcache同时指向它；对于分离缓存，分别初始化c1作为指令缓存、c2作为数据缓存。

初始化过程包括计算组数、设置索引掩码偏移量为块大小的对数、构造索引掩码用于地址解析，并为每组分配LRU头尾指针和内容计数器。

#sourcecode[```c
void init_cache() {
  int i;
  /* Initialize statistics */
  cache_stat_inst.accesses = 0;
  cache_stat_inst.misses = 0;
  cache_stat_inst.replacements = 0;
  cache_stat_inst.demand_fetches = 0;
  cache_stat_inst.copies_back = 0;
  // ... data stats similarly

  if (cache_split) {
    /* Initialize instruction cache */
    c1.size = cache_isize;
    c1.associativity = cache_assoc;
    c1.n_sets = cache_isize / (cache_block_size * cache_assoc);
    c1.index_mask_offset = LOG2(cache_block_size);
    c1.index_mask = (c1.n_sets - 1) << c1.index_mask_offset;
    
    c1.LRU_head = (Pcache_line *)calloc(c1.n_sets, sizeof(Pcache_line));
    c1.LRU_tail = (Pcache_line *)calloc(c1.n_sets, sizeof(Pcache_line));
    c1.set_contents = (int *)calloc(c1.n_sets, sizeof(int));
    icache = &c1;
    // ... similarly for c2 as dcache
  } else {
    /* Unified cache: icache and dcache point to same structure */
    c1.n_sets = cache_usize / (cache_block_size * cache_assoc);
    // ... initialize c1
    icache = &c1;
    dcache = &c1;
  }
}
```]

组数计算公式为 $ n_"sets" = "cache size" / ("block size" times "associativity") $ 索引掩码的构造通过将`(n_sets - 1)`左移`index_mask_offset`位实现，其中偏移量等于块大小的对数。对于8KB缓存、16字节块、直接映射的配置，组数为512，索引掩码为`0x1FF0`（9位索引左移4位）。统一缓存模式下icache和dcache指向同一结构体，实现指令和数据共享缓存空间。

== perform_access函数实现

该函数是缓存模拟的核心。我们首先实现基础的统一缓存直接映射功能，然后逐步添加可变关联度、写策略和指令数据分离统计等功能。

=== 基础功能

首先根据访问类型确定使用指令缓存还是数据缓存，以及对应的统计结构体。地址解析通过索引掩码提取组索引，通过移位操作提取标签。32位地址被划分为三部分：低位的块内偏移、中间的组索引、高位的标签。

#sourcecode[```c
void perform_access(addr, access_type)
  unsigned addr, access_type;
{
  unsigned index, tag;
  Pcache c;
  Pcache_stat stat;
  
  /* Select cache and stats based on access type */
  if (access_type == TRACE_INST_LOAD) {
    c = icache; stat = &cache_stat_inst; is_write = FALSE;
  } else {
    c = dcache; stat = &cache_stat_data;
    is_write = (access_type == TRACE_DATA_STORE);
  }
  stat->accesses++;
  
  /* Calculate index and tag from address */
  index = (addr & c->index_mask) >> c->index_mask_offset;
  tag = addr >> (c->index_mask_offset + LOG2(c->n_sets));
```]

通过`index_mask`与地址按位与后右移可得组索引，将地址右移`(index_mask_offset + LOG2(n_sets))`位可得标签。若缓存组为空，说明未命中，需要动态分配一个cache块并更新统计信息；否则遍历链表查找匹配的标签。

=== 可变关联度与LRU替换

这一步骤基于双向链表实现组相联缓存的LRU替换策略。

缓存查找遍历目标组的LRU链表，若标签匹配则命中，将该行移至链表头部表示最近使用。每个组通过`set_contents`记录有效条目数，当组已满时选择链表尾部（即最久未使用）的块进行替换。

#sourcecode[```c
  /* Search for hit in the cache set */
  line = c->LRU_head[index];
  while (line != NULL) {
    if (line->tag == tag) {
      /* Cache hit: update LRU order */
      delete(&c->LRU_head[index], &c->LRU_tail[index], line);
      insert(&c->LRU_head[index], &c->LRU_tail[index], line);
      if (is_write) {
        line->dirty = TRUE;
        if (!cache_writeback) stat->copies_back++;  /* Write through */
      }
      return;
    }
    line = line->LRU_next;
  }
```]

命中时调用`delete`和`insert`将该行移至链表头部。

=== 写策略与dirty位管理

这一步骤实现写回(WB)、写直通(WT)和写分配(WA)、非写分配(WNA)策略。写命中时设置dirty标志位，写直通模式下同时累加写回流量。写缺失时，非写分配模式直接写入内存而不分配缓存行；写分配模式则先取入数据块再写入。替换时，若被驱逐块的dirty位为1且采用写回策略，则需将数据写回内存并累加写回流量。

#sourcecode[```c
  /* Cache miss */
  stat->misses++;
  
  /* Write miss with no-write-allocate: write directly to memory */
  if (is_write && !cache_writealloc) {
    stat->copies_back++;
    return;
  }
  
  /* Fetch block from memory */
  stat->demand_fetches += words_per_block;
  
  /* Evict LRU line if set is full */
  if (c->set_contents[index] >= c->associativity) {
    stat->replacements++;
    line = c->LRU_tail[index];
    if (line->dirty && cache_writeback)
      stat->copies_back += words_per_block;  /* Write back dirty block */
    delete(&c->LRU_head[index], &c->LRU_tail[index], line);
    new_line = line;  /* Reuse evicted line structure */
  } else {
    new_line = (Pcache_line)malloc(sizeof(cache_line));
  }
  
  /* Initialize and insert new line */
  new_line->tag = tag;
  new_line->dirty = is_write;
  insert(&c->LRU_head[index], &c->LRU_tail[index], new_line);
  c->set_contents[index]++;
}
```]

缺失处理体现了写策略的差异。写回模式下脏块在被驱逐时才写回内存（每次写回`words_per_block`字），写直通模式下每次写操作都立即写回。新分配或复用的缓存行根据访问类型设置dirty标志，数据写时置为TRUE，读操作时置为FALSE。

== flush函数实现

该函数在模拟结束时遍历所有缓存行，将脏块写回内存。对于分离缓存需分别遍历指令缓存和数据缓存，统一缓存则仅遍历dcache（与icache指向同一结构）。遍历过程中检查每行的脏位，若为脏且采用写回策略，则累加对应统计结构体的写回字数，并清除脏位。

#sourcecode[```c
void flush() {
  int i;
  Pcache_line line;
  
  /* Flush instruction cache (only if split cache) */
  if (cache_split) {
    for (i = 0; i < icache->n_sets; i++) {
      line = icache->LRU_head[i];
      while (line != NULL) {
        if (line->dirty && cache_writeback) {
          cache_stat_inst.copies_back += words_per_block;
          line->dirty = FALSE;
        }
        line = line->LRU_next;
      }
    }
  }
  
  /* Flush data cache (or unified cache) */
  for (i = 0; i < dcache->n_sets; i++) {
    line = dcache->LRU_head[i];
    while (line != NULL) {
      if (line->dirty && cache_writeback) {
        cache_stat_data.copies_back += words_per_block;
        line->dirty = FALSE;
      }
      line = line->LRU_next;
    }
  }
}
```]

`flush`函数确保模拟结束时所有脏数据都被统计到写回流量中。这对于写回策略尤为重要，因为脏块可能在程序结束时仍驻留在缓存中。统一缓存模式下icache和dcache指向同一结构，因此仅遍历dcache即可覆盖所有缓存行。

= 实验测试与验证

== 测试配置

基本测试配置采用8KB统一缓存、16字节块大小、直接映射（关联度1）、写回策略和写分配策略。使用Python脚本自动化运行多组测试，包括公开测试用例、参数变化测试。测试命令如下：

#sourcecode[```bash
./sim -bs 16 -us 8192 -a 1 -wb -wa traces/spice100.trace
```]

== 测试结果

对于spice100.trace的基本配置测试，指令访问71次缺失20次（缺失率28.17%），数据访问29次缺失11次（缺失率37.93%），总计需求取回124字、写回12字。测试输出示例：

#sourcecode[```
*** CACHE SETTINGS ***
  Unified I- D-cache
  Size:         8192
  Associativity:        1
  Block size:   16
  Write policy:         WRITE BACK
  Allocation policy:    WRITE ALLOCATE

*** CACHE STATISTICS ***
 INSTRUCTIONS
  accesses:  71
  misses:    20
  miss rate: 0.2817 (hit rate 0.7183)
  replace:   1
 DATA
  accesses:  29
  misses:    11
  miss rate: 0.3793 (hit rate 0.6207)
  replace:   0
 TRAFFIC (in words)
  demand fetch:  124
  copies back:   12
```]

不同块大小测试显示，块大小增加可降低缺失率，但增加传输流量。不同关联度测试表明在该跟踪下关联度变化对性能影响有限。写策略对比显示写直通非写分配模式下数据缺失率略高（44.83%），但总流量可能更低。
== 验证

模拟器输出与预期行为一致：命中时正确更新LRU顺序，缺失时正确处理替换和写回，统计数据符合缓存工作原理。验证要点包括：需求取回字数等于缺失次数乘以每块字数，写回字数在写回模式下等于脏块驱逐次数乘以每块字数加上flush时的脏块数乘以每块字数。

为便于测试和验证，编写了两个Python脚本。

`run_tests.py`用于自动运行多种配置的测试用例，包括公开测试集、不同块大小测试、不同关联度测试、写策略对比以及分离缓存测试，用于快速验证模拟器的基本功能。

为了直观地验证和展示模拟器输出的正确性，创建`validate.py`用于严格验证模拟器输出与sim.pdf中Table 1的22组预期值是否完全一致，可直观表示模拟器工作正常与否。

#image("pics/table1.png")
`validate.py`运行测试结果如下：
#image("pics/table1结果.png")

验证结果表明所有22组测试全部通过，指令缺失次数、指令替换次数、数据缺失次数、数据替换次数、需求取回字数和写回字数均与预期值完全一致。


= 任务二：性能评估

- characterize the working set size of the three sample traces given.
- evaluate the Impact of Block Size on performance
- evaluate the Impact of Associativity on performance
- evaluate the Impact of Memory Bandwidth on performance

== 实验2-1：工作集特征

本实验旨在确定程序的指令和数据工作集大小。采用分离式缓存、全相联配置、4字节块大小、写回+写分配策略。通过逐步增大缓存容量，观察命中率变化趋势。当命中率趋于稳定时，对应的缓存大小即为工作集大小的近似值。

使用Python脚本`exp2_1_workingset.py`自动化测试。脚本遍历从4B到1MB的缓存大小，对每个大小运行模拟器，解析输出中的命中率，最后用matplotlib绘制曲线图。三个trace文件（spice、cc、tex）的指令和数据命中率分别绘制在两张子图中，便于对比分析。

#image("pics/exp2_1_workingset.png")

=== 问题1：实验原理

本实验通过模拟不同缓存大小对命中率的影响来评估工作集大小。工作集是指在一定时间内被频繁访问的内存块集合。实验使用全相联缓存排除冲突缺失的影响，使所有缺失均为强制缺失或容量缺失，从而准确反映工作集特征。

命中率与缓存大小图表呈现三个典型阶段：
- 初始快速上升阶段表明工作集大小超过当前缓存，增加缓存可显著提高命中率；
- 逐渐平缓阶段表明接近工作集大小；
- 趋于平稳阶段表明工作集已被完全包含，进一步增加缓存不会提高命中率。

=== 问题2：大小估计

根据实验结果可估计：
- spice.trace：指令工作集约16KB，数据工作集约16KB
- cc.trace：指令工作集约32KB，数据工作集约8KB
- tex.trace：指令工作集约512B，数据工作集约128B

指令工作集通常大于数据工作集，因为程序代码的访问范围较广。不同程序的工作集大小差异明显，反映了其内存访问模式的不同特征。

== 实验2-2：块大小影响

本实验分析块大小对缓存性能的影响。采用分离式缓存、I-Cache和D-Cache各8KB、2路组相联、写回+写分配策略。块大小从4字节变化到4KB。较大的块大小利用空间局部性，可预取相邻数据减少缺失率；但过大的块大小会减少组数、增加冲突缺失，且增大传输开销。

使用Python脚本`exp2_2_blocksize.py`自动化测试。遍历4B到4KB的11个块大小，对每个配置运行模拟器并解析命中率，最后用matplotlib绘制曲线图。

#image("pics/exp2_2_blocksize.png")

=== 问题1：曲线形状

命中率随块大小呈现先上升后下降的趋势，这与空间局部性密切相关。块大小较小时，增大块可以利用空间局部性预取相邻数据，减少强制缺失，因此命中率上升。但块大小过大时，组数减少导致冲突缺失增加，且每次缺失需传输更多数据，包括未必使用的部分，导致总体性能下降。因此曲线存在一个峰值，对应最优块大小。

=== 问题2：各trace最优块大小

根据实验结果，不同trace的最优块大小如下：

- spice.trace指令缓存最优块大小约512B，数据缓存约32B；

- cc.trace指令缓存约2KB，数据缓存约32B；

- tex.trace指令缓存在2KB之前都基本稳定不变，直到4KB开始下降；数据缓存约128B。

具体数值取决于程序的访问模式，但总体而言最优块大小在几十到几百字节范围内。

=== 问题3：差异分析

指令缓存的最优块大小通常大于数据缓存，这反映了指令和数据访问模式的本质差异。指令流主要是顺序执行，具有很强的空间局部性，较大的块可以有效预取后续指令；而数据访问模式更不规则，包括数组遍历、指针跳转、结构体访问等，空间局部性较差，过大的块会带来更多无用数据传输和冲突缺失。

== 实验2-3：相联度影响

本实验分析相联度对缓存性能的影响。采用分离式缓存、I-Cache和D-Cache各8KB、128字节块大小、写回+写分配策略。相联度从1（直接映射）变化到64。

使用Python脚本`exp2_3_associativity.py`自动化测试。脚本遍历相联度配置，对每个配置运行模拟器并解析命中率。纵坐标紧贴数据范围，使曲线变化更加明显。

#image("pics/exp2_3_associativity.png")

=== 问题1：曲线形状

命中率随相联度增加而上升，但边际效益递减。这是因为增加相联度可以减少冲突缺失，当多个地址映射到同一组时，更高的相联度提供更多缓存行来容纳这些块，避免互相驱逐。

曲线初期上升较快，说明直接映射（相联度1）时冲突缺失较严重；后期趋于平缓，说明大部分冲突已被消除，继续增加相联度收益有限。实际应用中通常采用2-8路组相联，在性能和硬件复杂度间取得平衡。

比较特殊的是 tex.trace 的 icache 图，命中率随着关联度几乎保持在 100%，说明该程序的指令引用具有很好的空间局部性，无论关联度如何，都能被缓存很好地覆盖。

=== 问题2：差异分析

对于指令和数据引用，命中率随着关联度的增加而上升；在达到一定关联度后，命中率的提升趋于平缓。但具体的几个阈值对于指令和数据引用可能有所不同。某些情况下，过高的关联度可能导致命中率略有下降，这在指令和数据引用中的表现可能不一致。

数据缓存从相联度增加中获益更多，这反映了指令和数据访问模式的差异。

指令流主要是顺序执行和局部跳转，地址分布较为规则，冲突缺失相对较少，因此低相联度即可获得较高命中率；而数据访问包括数组遍历、指针跳转、栈操作等，地址分布更不规则，容易产生冲突缺失，因此更能从高相联度中受益。所以现代处理器的D-Cache相联度通常高于I-Cache。

== 实验2-4：内存带宽分析

本实验对比不同写策略对内存流量的影响。采用分离缓存，缓存大小8K/16K，块大小64/128B，相联度2/4。实验A比较写直通(WT)与写回(WB)策略，固定非写分配(NW)；实验B比较WA与NW策略，固定WB。

使用Python脚本`exp2_4_bandwidth.py`自动化测试。流量统计结果如下：

#image("pics/exp2_4_table_a.png")

#image("pics/exp2_4_table_b.png")

=== 实验A问题1：WT vs WB流量比较

WB策略产生更少的内存流量。原因是写直通每次写操作都直接写入内存，而写回只在脏块被驱逐时才写回。当同一块被多次写入时，写回模式可将多次写操作合并为一次写回，大大减少内存流量。

=== 实验A问题2：WT更优

当写操作非常稀疏且每个块只被写一次时，WT可能更优。因为WT每次只写一个字，而WB在驱逐时需写回整个块。

在某些系统中，数据一致性要求很高，需要确保每次写操作后数据立即更新到主存。在这种情况下，WT可以减少由于数据一致性问题而导致的额外内存流量。

如果缓存替换非常频繁，WB可能会导致大量的写回操作，从而增加内存流量。而WT每次写操作都立即写回主存，避免了替换时的写回操作。

但在实际程序中，写操作通常具有时间、空间局部性，同一块多次写入很常见，因此WB通常更优。

=== 实验B问题1：WA vs NW流量比较

结果取决于程序特征。WA在写缺失时需取入整个块，增加demand fetch；NW直接写内存，不增加fetch但增加copies back。当写入的数据很快被读取时，WA更优（已在缓存）；当写入后不再访问时，NW更优（避免无用fetch）。

=== 实验B问题2：答案反转

当程序表现出写后读模式时，WA更优，因为数据已在缓存中。当程序主要是只写模式如日志输出、结果存储时，NW更优，因为避免了不必要的块取入。实验结果显示，大多数情况下NW略优，说明写操作后续读取较少。

