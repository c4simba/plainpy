/* KolibriOS platform hooks: runtime relocation, process-heap init, page
   allocator, console lifecycle. */

#include "targets/platform.h"
#include "util.h"

/* The memory of plainpy on KolibriOS (libc malloc crashes without TLS setup).
   Function 68.12 hands out whole pages and costs a system call (68.13 another to give
   them back), so a block of up to 2 KB comes from a size class: carved out of 256 KB
   chunks of 68.12, back on its class's free list when freed (kept for the next one);
   a bigger block is a 68.12 block of its own.
   f68.12: eax=68, ebx=12, ecx=bytes          -> allocate (whole pages, page-aligned)
   f68.13: eax=68, ebx=13, ecx=block          -> free a block from f68.12
   Every block: [ magic(4) | class(4): 0 own block, else 1.. | size asked(4) | room(4) ][ payload ]
   (16 bytes, so the payload stays 16-aligned); the header lets realloc copy the right
   amount and stay in place while the new size fits. Threads: one lock around it. */
#define KOS_HEAD   16u
#define KOS_MAGIC  0x484f534bu   /* 'KOSH' */
#define KOS_FREED  0x45455246u   /* 'FREE': on a free list (a second free is a no-op) */
#define KOS_CHUNK  (256u*1024u)
static const unsigned kos_class_size[]={16,32,48,64,80,96,112,128,160,192,224,256,320,384,448,512,640,768,896,1024,1280,1536,1792,2048};
#define KOS_NCLASS ((int)(sizeof kos_class_size/sizeof kos_class_size[0]))
static void *kos_free_list[KOS_NCLASS];
static char *kos_chunk_at, *kos_chunk_end;
static ppy_lock kos_heap_lock;

static void *kos_pages(size_t bytes){
    void *base;
    __asm__ __volatile__("int $0x40" : "=a"(base) : "a"(68), "b"(12), "c"(bytes) : "memory");
    if(!base || (int)base <= 0) die("out of memory");
    return base;
}
static int kos_class_of(size_t n){
    if(n > 2048) return -1;
    int lo=0, hi=KOS_NCLASS-1;                 /* the smallest class that holds n */
    while(lo < hi){ int mid=(lo+hi)/2; if(kos_class_size[mid] >= n) hi=mid; else lo=mid+1; }
    return lo;
}

void *kos_malloc(size_t n){
    int c = kos_class_of(n);
    unsigned *base;
    if(c < 0){
        size_t total = (n + KOS_HEAD + 4095) & ~(size_t)4095;
        base = (unsigned*)kos_pages(total);
        base[0] = KOS_MAGIC; base[1] = 0; base[2] = (unsigned)n; base[3] = (unsigned)(total - KOS_HEAD);
        return (char*)base + KOS_HEAD;
    }
    ppy_lock_acquire(&kos_heap_lock);
    base = (unsigned*)kos_free_list[c];
    if(base) kos_free_list[c] = *(void**)((char*)base + KOS_HEAD);
    else {
        size_t size = KOS_HEAD + kos_class_size[c];
        if(!kos_chunk_at || (size_t)(kos_chunk_end - kos_chunk_at) < size){
            kos_chunk_at = (char*)kos_pages(KOS_CHUNK);
            kos_chunk_end = kos_chunk_at + KOS_CHUNK;
        }
        base = (unsigned*)kos_chunk_at;
        kos_chunk_at += size;
    }
    ppy_lock_release(&kos_heap_lock);
    base[0] = KOS_MAGIC; base[1] = (unsigned)c + 1; base[2] = (unsigned)n; base[3] = kos_class_size[c];
    return (char*)base + KOS_HEAD;
}

void *kos_calloc(size_t n, size_t size){
    if(size && n > (size_t)-1 / size) return NULL;
    void *p = kos_malloc(n * size);
    memset(p, 0, n * size);
    return p;
}

void kos_free(void *p){
    if(!p) return;
    unsigned *base = (unsigned*)((char*)p - KOS_HEAD);
    if(base[0] != KOS_MAGIC) return;   /* not ours (foreign/libc pointer) or freed already: leave it */
    if(base[1] == 0){
        base[0] = 0;
        __asm__ __volatile__("int $0x40" :: "a"(68), "b"(13), "c"(base) : "memory");
        return;
    }
    int c = (int)base[1] - 1;
    base[0] = KOS_FREED;
    ppy_lock_acquire(&kos_heap_lock);
    *(void**)p = kos_free_list[c];
    kos_free_list[c] = base;
    ppy_lock_release(&kos_heap_lock);
}

void *kos_realloc(void *p, size_t n){
    if(!p) return kos_malloc(n);
    unsigned *base = (unsigned*)((char*)p - KOS_HEAD);
    if(base[0] == KOS_MAGIC && n <= base[3] && (base[1] == 0 || n > base[3] / 2 || n <= 16)){
        base[2] = (unsigned)n;         /* (it fits - and does not leave most of a small block unused) */
        return p;
    }
    void *np = kos_malloc(n);
    size_t old = (base[0] == KOS_MAGIC) ? base[2] : n;
    memcpy(np, p, old < n ? old : n);
    kos_free(p);
    return np;
}

extern void _pei386_runtime_relocator(void);

void ppy_platform_init(void){
    fprintf(stderr, "[plainpy] start\n"); fflush(stderr);
    fprintf(stderr, "[plainpy] calling reloc\n"); fflush(stderr);
    _pei386_runtime_relocator();
    fprintf(stderr, "[plainpy] reloc ok\n"); fflush(stderr);
    /* Initialize process heap (required before any malloc) - f68.11 */
    {
        int heap_ptr;
        __asm__ __volatile__("int $0x40"
            : "=a"(heap_ptr)
            : "a"(68), "b"(11)
            : "memory");
        fprintf(stderr, "[plainpy] heap init: ptr=0x%x\n", heap_ptr);
        fflush(stderr);
    }
    /* Bring the console up now (needs the heap) so *all* output -- including
       early exits like -v/--version and usage -- is visible, not just script
       output printed after the banner. Idempotent; the banner may call it too. */
    kol_console_init();
}

void ppy_platform_shutdown(void){
    kol_console_deinit();
}

#ifndef PPY_FS_DEFAULT_IMPORT_DIR
#define PPY_FS_DEFAULT_IMPORT_DIR "."
#endif
#ifndef PPY_DEFAULT_SCRIPT
#define PPY_DEFAULT_SCRIPT PPY_FS_DEFAULT_IMPORT_DIR "/main.py"
#endif

const char *ppy_platform_default_script(void){ return PPY_DEFAULT_SCRIPT; }

/* MENUET header buffers (see kos-app-fix.lds): the kernel copies the launch
   command line into ___kosapp_cmdline and the program path into ___kosapp_name.
   The PE toolchain prepends one underscore, so the C names carry two. */
extern char __kosapp_cmdline[];
extern char __kosapp_name[];
const char *ppy_platform_cmdline(void){ return __kosapp_cmdline; }
const char *ppy_platform_exe_path(void){ return __kosapp_name; }
void ppy_platform_make_executable(const char *path){ (void)path; }

void ppy_platform_banner(const char *script_path){
    kol_console_init();
    kol_console_puts("PlainPy - KolibriOS\n\r");
    kol_console_puts(script_path ? script_path : "(default)");
    kol_console_puts("\n\r");
}

int ppy_platform_exec(const char *path, char **argv){
    static char args[1024]; size_t n=0;                      /* (its arguments as one string: KolibriOS has no argv) */
    for(int i=1;argv[i];i++){
        size_t l=strlen(argv[i]); int quote=strchr(argv[i],' ')!=NULL;
        if(n+l+4>=sizeof args) break;
        if(n) args[n++]=' ';
        if(quote) args[n++]='"';
        memcpy(args+n,argv[i],l); n+=l;
        if(quote) args[n++]='"';
    }
    args[n]=0;
    return ppy_platform_run(path,args)<0 ? -1 : 0;
}

/* f70.7 starts the program; KolibriOS has no wait(), so poll fn 18.21 (slot of
   a PID, 0 once the process is gone) until it exits. */
int ppy_platform_run(const char *program, const char *args){
    unsigned char bi[300] __attribute__((aligned(16)));
    memset(bi, 0, sizeof bi);
    *(int*)(bi + 0) = 7;               /* subfunction: start program */
    *(int*)(bi + 8) = (int)args;       /* parameter string */
    size_t plen = strlen(program);
    if(plen > sizeof bi - 21) plen = sizeof bi - 21;
    memcpy(bi + 20, program, plen);
    int pid;
    __asm__ __volatile__("int $0x40" : "=a"(pid) : "a"(70), "b"((int)bi) : "memory");
    if(pid <= 0) return pid ? pid : -1;
    for(;;){
        int slot;
        __asm__ __volatile__("int $0x40" : "=a"(slot) : "a"(18), "b"(21), "c"(pid) : "memory");
        if(slot == 0) return 0;
        __asm__ __volatile__("int $0x40" :: "a"(5), "b"(5) : "memory");   /* 50 ms */
    }
}
