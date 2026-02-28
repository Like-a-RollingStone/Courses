/*
 * cache.c
 */


#include <stdlib.h>
#include <stdio.h>
#include <math.h>

#include "cache.h"
#include "main.h"

/* cache configuration parameters */
static int cache_split = 0;
static int cache_usize = DEFAULT_CACHE_SIZE;
static int cache_isize = DEFAULT_CACHE_SIZE; 
static int cache_dsize = DEFAULT_CACHE_SIZE;
static int cache_block_size = DEFAULT_CACHE_BLOCK_SIZE;
static int words_per_block = DEFAULT_CACHE_BLOCK_SIZE / WORD_SIZE;
static int cache_assoc = DEFAULT_CACHE_ASSOC;
static int cache_writeback = DEFAULT_CACHE_WRITEBACK;
static int cache_writealloc = DEFAULT_CACHE_WRITEALLOC;

/* cache model data structures */
static Pcache icache;
static Pcache dcache;
static cache c1;
static cache c2;
static cache_stat cache_stat_inst;
static cache_stat cache_stat_data;

/************************************************************/
void set_cache_param(param, value)
  int param;
  int value;
{

  switch (param) {
  case CACHE_PARAM_BLOCK_SIZE:
    cache_block_size = value;
    words_per_block = value / WORD_SIZE;
    break;
  case CACHE_PARAM_USIZE:
    cache_split = FALSE;
    cache_usize = value;
    break;
  case CACHE_PARAM_ISIZE:
    cache_split = TRUE;
    cache_isize = value;
    break;
  case CACHE_PARAM_DSIZE:
    cache_split = TRUE;
    cache_dsize = value;
    break;
  case CACHE_PARAM_ASSOC:
    cache_assoc = value;
    break;
  case CACHE_PARAM_WRITEBACK:
    cache_writeback = TRUE;
    break;
  case CACHE_PARAM_WRITETHROUGH:
    cache_writeback = FALSE;
    break;
  case CACHE_PARAM_WRITEALLOC:
    cache_writealloc = TRUE;
    break;
  case CACHE_PARAM_NOWRITEALLOC:
    cache_writealloc = FALSE;
    break;
  default:
    printf("error set_cache_param: bad parameter value\n");
    exit(-1);
  }

}
/************************************************************/

/************************************************************/
void init_cache()
{
  int i;

  /* initialize the cache, and cache statistics data structures */
  
  /* Initialize statistics */
  cache_stat_inst.accesses = 0;
  cache_stat_inst.misses = 0;
  cache_stat_inst.replacements = 0;
  cache_stat_inst.demand_fetches = 0;
  cache_stat_inst.copies_back = 0;
  
  cache_stat_data.accesses = 0;
  cache_stat_data.misses = 0;
  cache_stat_data.replacements = 0;
  cache_stat_data.demand_fetches = 0;
  cache_stat_data.copies_back = 0;

  if (cache_split) {
    /* Split I-cache and D-cache */
    
    /* Initialize instruction cache */
    c1.size = cache_isize;
    c1.associativity = cache_assoc;
    c1.n_sets = cache_isize / (cache_block_size * cache_assoc);
    c1.index_mask_offset = LOG2(cache_block_size);
    c1.index_mask = (c1.n_sets - 1) << c1.index_mask_offset;
    
    c1.LRU_head = (Pcache_line *)calloc(c1.n_sets, sizeof(Pcache_line));
    c1.LRU_tail = (Pcache_line *)calloc(c1.n_sets, sizeof(Pcache_line));
    c1.set_contents = (int *)calloc(c1.n_sets, sizeof(int));
    c1.contents = 0;
    
    for (i = 0; i < c1.n_sets; i++) {
      c1.LRU_head[i] = NULL;
      c1.LRU_tail[i] = NULL;
      c1.set_contents[i] = 0;
    }
    
    icache = &c1;
    
    /* Initialize data cache */
    c2.size = cache_dsize;
    c2.associativity = cache_assoc;
    c2.n_sets = cache_dsize / (cache_block_size * cache_assoc);
    c2.index_mask_offset = LOG2(cache_block_size);
    c2.index_mask = (c2.n_sets - 1) << c2.index_mask_offset;
    
    c2.LRU_head = (Pcache_line *)calloc(c2.n_sets, sizeof(Pcache_line));
    c2.LRU_tail = (Pcache_line *)calloc(c2.n_sets, sizeof(Pcache_line));
    c2.set_contents = (int *)calloc(c2.n_sets, sizeof(int));
    c2.contents = 0;
    
    for (i = 0; i < c2.n_sets; i++) {
      c2.LRU_head[i] = NULL;
      c2.LRU_tail[i] = NULL;
      c2.set_contents[i] = 0;
    }
    
    dcache = &c2;
    
  } else {
    /* Unified cache */
    c1.size = cache_usize;
    c1.associativity = cache_assoc;
    c1.n_sets = cache_usize / (cache_block_size * cache_assoc);
    c1.index_mask_offset = LOG2(cache_block_size);
    c1.index_mask = (c1.n_sets - 1) << c1.index_mask_offset;
    
    c1.LRU_head = (Pcache_line *)calloc(c1.n_sets, sizeof(Pcache_line));
    c1.LRU_tail = (Pcache_line *)calloc(c1.n_sets, sizeof(Pcache_line));
    c1.set_contents = (int *)calloc(c1.n_sets, sizeof(int));
    c1.contents = 0;
    
    for (i = 0; i < c1.n_sets; i++) {
      c1.LRU_head[i] = NULL;
      c1.LRU_tail[i] = NULL;
      c1.set_contents[i] = 0;
    }
    
    icache = &c1;
    dcache = &c1;
  }
}
/************************************************************/

/************************************************************/
void perform_access(addr, access_type)
  unsigned addr, access_type;
{
  unsigned index, tag;
  Pcache c;
  Pcache_stat stat;
  Pcache_line line, new_line;
  int is_write;
  
  /* Determine which cache and stats to use */
  if (access_type == TRACE_INST_LOAD) {
    c = icache;
    stat = &cache_stat_inst;
    is_write = FALSE;
  } else {
    c = dcache;
    stat = &cache_stat_data;
    is_write = (access_type == TRACE_DATA_STORE);
  }
  
  /* Update access count */
  stat->accesses++;
  
  /* Calculate index and tag */
  index = (addr & c->index_mask) >> c->index_mask_offset;
  tag = addr >> (c->index_mask_offset + LOG2(c->n_sets));
  
  /* Search for hit in the cache set */
  line = c->LRU_head[index];
  while (line != NULL) {
    if (line->tag == tag) {
      /* Cache hit */
      /* Move to head of LRU list (most recently used) */
      delete(&c->LRU_head[index], &c->LRU_tail[index], line);
      insert(&c->LRU_head[index], &c->LRU_tail[index], line);
      
      /* Set dirty bit on write */
      if (is_write) {
        line->dirty = TRUE;
        if (!cache_writeback) {
          /* Write through: write to memory immediately */
          stat->copies_back++;
        }
      }
      return;
    }
    line = line->LRU_next;
  }
  
  /* Cache miss */
  stat->misses++;
  
  /* Handle write miss with no-write-allocate */
  if (is_write && !cache_writealloc) {
    /* Write directly to memory, don't allocate cache line */
    stat->copies_back++;
    return;
  }
  
  /* Fetch block from memory */
  stat->demand_fetches += words_per_block;
  
  /* Check if we need to evict */
  if (c->set_contents[index] >= c->associativity) {
    /* Need to replace - evict LRU (tail) */
    stat->replacements++;
    line = c->LRU_tail[index];
    
    /* Write back dirty block */
    if (line->dirty && cache_writeback) {
      stat->copies_back += words_per_block;
    }
    
    /* Remove from LRU list and reuse */
    delete(&c->LRU_head[index], &c->LRU_tail[index], line);
    c->set_contents[index]--;
    c->contents--;
    
    /* Reuse the cache line */
    new_line = line;
  } else {
    /* Allocate new cache line */
    new_line = (Pcache_line)malloc(sizeof(cache_line));
  }
  
  /* Initialize the new cache line */
  new_line->tag = tag;
  new_line->dirty = FALSE;
  new_line->LRU_next = NULL;
  new_line->LRU_prev = NULL;
  
  /* Set dirty bit if write */
  if (is_write) {
    new_line->dirty = TRUE;
    if (!cache_writeback) {
      /* Write through */
      stat->copies_back++;
    }
  }
  
  /* Insert at head of LRU list */
  insert(&c->LRU_head[index], &c->LRU_tail[index], new_line);
  c->set_contents[index]++;
  c->contents++;
}
/************************************************************/

/************************************************************/
void flush()
{
  int i;
  Pcache_line line;
  
  /* flush the cache - write back all dirty blocks */
  
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
/************************************************************/

/************************************************************/
void delete(head, tail, item)
  Pcache_line *head, *tail;
  Pcache_line item;
{
  if (item->LRU_prev) {
    item->LRU_prev->LRU_next = item->LRU_next;
  } else {
    /* item at head */
    *head = item->LRU_next;
  }

  if (item->LRU_next) {
    item->LRU_next->LRU_prev = item->LRU_prev;
  } else {
    /* item at tail */
    *tail = item->LRU_prev;
  }
}
/************************************************************/

/************************************************************/
/* inserts at the head of the list */
void insert(head, tail, item)
  Pcache_line *head, *tail;
  Pcache_line item;
{
  item->LRU_next = *head;
  item->LRU_prev = (Pcache_line)NULL;

  if (item->LRU_next)
    item->LRU_next->LRU_prev = item;
  else
    *tail = item;

  *head = item;
}
/************************************************************/

/************************************************************/
void dump_settings()
{
  printf("*** CACHE SETTINGS ***\n");
  if (cache_split) {
    printf("  Split I- D-cache\n");
    printf("  I-cache size: \t%d\n", cache_isize);
    printf("  D-cache size: \t%d\n", cache_dsize);
  } else {
    printf("  Unified I- D-cache\n");
    printf("  Size: \t%d\n", cache_usize);
  }
  printf("  Associativity: \t%d\n", cache_assoc);
  printf("  Block size: \t%d\n", cache_block_size);
  printf("  Write policy: \t%s\n", 
	 cache_writeback ? "WRITE BACK" : "WRITE THROUGH");
  printf("  Allocation policy: \t%s\n",
	 cache_writealloc ? "WRITE ALLOCATE" : "WRITE NO ALLOCATE");
}
/************************************************************/

/************************************************************/
void print_stats()
{
  printf("\n*** CACHE STATISTICS ***\n");

  printf(" INSTRUCTIONS\n");
  printf("  accesses:  %d\n", cache_stat_inst.accesses);
  printf("  misses:    %d\n", cache_stat_inst.misses);
  if (!cache_stat_inst.accesses)
    printf("  miss rate: 0 (0)\n"); 
  else
    printf("  miss rate: %2.4f (hit rate %2.4f)\n", 
	 (float)cache_stat_inst.misses / (float)cache_stat_inst.accesses,
	 1.0 - (float)cache_stat_inst.misses / (float)cache_stat_inst.accesses);
  printf("  replace:   %d\n", cache_stat_inst.replacements);

  printf(" DATA\n");
  printf("  accesses:  %d\n", cache_stat_data.accesses);
  printf("  misses:    %d\n", cache_stat_data.misses);
  if (!cache_stat_data.accesses)
    printf("  miss rate: 0 (0)\n"); 
  else
    printf("  miss rate: %2.4f (hit rate %2.4f)\n", 
	 (float)cache_stat_data.misses / (float)cache_stat_data.accesses,
	 1.0 - (float)cache_stat_data.misses / (float)cache_stat_data.accesses);
  printf("  replace:   %d\n", cache_stat_data.replacements);

  printf(" TRAFFIC (in words)\n");
  printf("  demand fetch:  %d\n", cache_stat_inst.demand_fetches + 
	 cache_stat_data.demand_fetches);
  printf("  copies back:   %d\n", cache_stat_inst.copies_back +
	 cache_stat_data.copies_back);
}
/************************************************************/
