#set page(margin: 2.2cm)
#set text(lang: "en")

= Project - Cache Organization and Performance Evaluation

In this assignment, you will become familiar with how caches work and how to evaluate
their performance. To achieve these goals, you will first build a cache simulator and validate its
correctness. Then you will use your cache simulator to study many different cache organizations
and management policies as discussed in lecture and in Chapter 5 of Hennessy & Patterson.

Section 1 will walk you through how to build the cache simulator, and section 2 will specify
the performance evaluation studies you will undertake using your simulator.

== 1 Cache Simulator

In the first part of this assignment, you will build a cache simulator. The type of simulator you will
build is known as a trace-driven simulator because it takes as input a trace of events, in this case
memory references. The trace, which we will provide for you, was acquired on another machine.
Once acquired, it can be used to drive simulation studies. In this assignment, the memory reference
events specified in the trace(s) we will give you will be used by your simulator to drive the movement
of data into and out of the cache, thus simulating its behavior. Trace-driven simulators are very
effective for studying caches.

Your cache simulator will be configurable based on arguments given at the command line, and
must support the following functionality:

- Total cache size
- Block size
- Unified vs. split I- and D-caches
- Associativity
- Write back vs. write through
- Write allocate vs. write no allocate

In addition to implementing the functionality listed above, your simulator must also collect
and report several statistics that will be used to verify the correctness of the simulator, and that
will be used for performance evaluation later in the assignment. In particular, your simulator must
track:

- Number of instruction references
- Number of data references
- Number of instruction misses
- Number of data misses
- Number of words fetched from memory
- Number of words copied back to memory

=== 1.1 Files

For your project, there are five program files in total, as indicated in table below which lists the
file names and a short description of their contents.

#table(
  columns: (1fr, 2fr),
  stroke: 0.6pt,
  inset: 6pt,
  align: (left, left),
  [*File Name*], [*Description*],
  [Makefile], [Builds the simulator.],
  [main.c], [Top-level routines for driving the simulator.],
  [main.h], [Header file for main.c.],
  [cache.c], [Cache model.],
  [cache.h], [Header file for cache.c.],
)

The “Makefile” is a UNIX make file. Try typing `make` in the local directory where you’ve
copied the files. This will build the simulator from the program files that have been provided, and
will produce an executable called “sim.” Of course, the executable doesn’t do very much since the
files we have given you are only a template for the simulator. However, you can use this make
file to build your simulator as you add functionality. Be sure to update the make file if you have
additional source files other than the four program files we’ve given you.

The four program files, `main.c`, `main.h`, `cache.c`, and `cache.h`, contain a template for the
simulator written in C. These files contain many useful routines that will save you time (since you
don’t have to write them yourself).

`main.c` contains the top-level driver for the simulator. It has a front-end routine called
`parse_args()` that parses command line arguments to allow configuring the cache model with
all the different parameters specified earlier. To see a list of valid command line arguments, try
typing `sim -h` (after compiling the template files). Note that your simulator code should interpret
the four size parameters, block size, unified cache size, instruction cache size, and data cache size,
in units of bytes.

`main.c` also contains a top-level “simulator loop,” called `play_trace()`, and a routine that
parses lines from the trace file, called `read_trace_element()`. For each trace element
read, `play_trace()` calls the cache model, via the routine `perform_access()`, to simulate a single
memory reference to the cache. While you are free to modify `main.c`, you should be able to
complete the assignment without making any modifications to this file.

`cache.c` contains the cache model itself. There are three routines in this file which you
should be able to use without modification.

- `set_cache_param()` is the cache model interface to the argument parsing routine in `main.c`.
  It intercepts all the parameter requests and sets the proper parameter values which have been
  declared as static globals in `cache.c`.
- `delete` and `insert` are deletion and insertion routines for a doubly linked list data structure,
  which we will explain below.
- `dump_settings()` prints the cache configuration based on the configured parameters, and
  `print_stats()` prints the statistics that you will gather.

In addition to these five routines, there are three template functions which you will have to write.

- `init_cache()` is called once to build and initialize the cache model data structures.
- `perform_access()` is called once for each iteration of the simulator loop to simulate a single
  memory reference to the cache.
- `flush()` is called at the very end of the simulation to purge the cache of its contents.

Note that the simulation is not finished until all dirty cache lines (if there are any) are flushed out
of the cache, and all statistics are updated as a result of such flushes.

`main.h` is self-explanatory. `cache.h` contains several constants for initializing and changing
the cache configuration, and contains the data structures used to implement the cache model (we
will explain these in the next section). Finally, `cache.h` also contains a macro for computing the
base-2 logarithm, called `LOG2`, which should become useful as you build the cache model.

In addition to the five program files, there are also three trace files that you will use to drive
your simulator. Their names are “spice.trace,” “cc.trace,” and “tex.trace.” These files are the result
of tracing the memory reference behavior of the spice circuit simulator, a C compiler, and the TeX
text formatting program, respectively. They represent roughly 1 million memory references each.

The trace files are in ASCII format, so they are in human-readable form. Each line in the
trace file represents a single memory reference and contains two numbers: a reference type, which is
a number between 0–2, and a memory address. All other text following these two numbers should
be ignored by your simulator.

The reference number specifies what type of memory reference is being performed with the
following encoding:

- `0` Data load reference
- `1` Data store reference
- `2` Instruction load reference

The number following the reference type is the byte address of the memory reference itself. This
number is in hexadecimal format, and specifies a 32-bit byte address in the range `0-0xffffffff`,
inclusive.

=== 1.2 Building the Cache Model

There are many ways to construct the cache model. You will be graded only on the correctness of
the model, so you are completely free to implement the cache model in any fashion you choose. In
this section, we give some hints for an implementation that uses the data structures given in the
template code.

==== 1.2.1 Incremental Approach

The most important hint is a general software engineering rule of thumb: build the simulator by
incrementally adding functionality. The biggest mistake you can make is to try to implement
the cache functions all at once. Instead, build the very simplest cache model possible, and test
it thoroughly before proceeding. Then, add a small piece of functionality, and then test that
thoroughly before proceeding. And so on until you’ve finished the assignment.

We recommend the following incremental approach:

1. Build a unified, fixed block size, direct-mapped cache with a write-back write policy and a
   write allocate allocation policy.
2. Add variable block size functionality.
3. Add variable associativity functionality.
4. Add split organization functionality.
5. Add write through write policy functionality.
6. Add write no-allocate allocation policy functionality.

You can test your cache model at each stage by comparing the results you get from your
simulator with the validation numbers which we will provide.

==== 1.2.2 Cache Structures

In `cache.h`, you will find the data structure `cache` which implements most of the cache model:

```c
typedef struct cache_ {
  int size;               /* cache size in words */
  int associativity;      /* cache associativity */
  int n_sets;             /* number of cache sets */
  unsigned index_mask;    /* mask to find cache index */
  int index_mask_offset;  /* number of zero bits in mask */
  Pcache_line *LRU_head;  /* head of LRU list for each set */
  Pcache_line *LRU_tail;  /* tail of LRU list for each set */
  int *set_contents;      /* number of valid entries in set */
} cache, *Pcache;
```
