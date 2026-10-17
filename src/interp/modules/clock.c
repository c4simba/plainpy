/* ========================= Interpreter, modules: _ppy_time =========================
   What time.py does most, in C for the interpreter (compiled programs have their own code
   for it): the clocks (clock_gettime; KolibriOS keeps time.py's), a struct_time made at
   once, the date of a day, and strftime of the usual directives (None: time.py does the
   rest - its text is the reference, this gives the same). */

#include "modules.h"
#include <time.h>

/* ---- the clocks: time.py's numbers (Linux's): 0 real time, 1 monotonic, 2 the process's CPU time, 3 the thread's */
#if !defined(PPY_KOLIBRI)
static struct timespec clk_read(int64_t clk){
    struct timespec ts;
    clockid_t id= clk==1 ? CLOCK_MONOTONIC : clk==2 ? CLOCK_PROCESS_CPUTIME_ID : clk==3 ? CLOCK_THREAD_CPUTIME_ID : CLOCK_REALTIME;
    clock_gettime(id,&ts);
    return ts;
}
#define CLOCK_FNS(name,clk) \
    static Value tm_##name(int argc, Value *argv, TupleObj *kw){ (void)argv; mod_no_kw(#name,kw); mod_nargs(#name,argc,0,0); \
        struct timespec ts=clk_read(clk); return v_float((double)ts.tv_sec+(double)ts.tv_nsec/1e9); } \
    static Value tm_##name##_ns(int argc, Value *argv, TupleObj *kw){ (void)argv; mod_no_kw(#name "_ns",kw); mod_nargs(#name "_ns",argc,0,0); \
        struct timespec ts=clk_read(clk); return v_int((int64_t)ts.tv_sec*1000000000+ts.tv_nsec); }
CLOCK_FNS(time,0) CLOCK_FNS(monotonic,1) CLOCK_FNS(process_time,2) CLOCK_FNS(thread_time,3)
static Value tm_clock(int argc, Value *argv, TupleObj *kw){           /* clock(clk): (seconds, nanoseconds) - time.py's _clock */
    mod_no_kw("clock",kw); mod_nargs("clock",argc,1,1);
    struct timespec ts=clk_read(mp_index(argv[0],"clock"));
    Value v[2]={v_int((int64_t)ts.tv_sec),v_int((int64_t)ts.tv_nsec)};
    return mp_tuple(2,v);
}
#endif

/* ---- dates */
static int64_t fdiv(int64_t a, int64_t b){ int64_t q=a/b; return (a%b!=0 && (a<0)!=(b<0)) ? q-1 : q; }   /* Python's // */
static int64_t days_from_civil(int64_t y, int64_t m, int64_t d){
    if(m<=2){ y-=1; m+=12; }
    int64_t era=fdiv(y,400), yoe=y-era*400, doy=fdiv(153*(m-3)+2,5)+d-1, doe=yoe*365+yoe/4-yoe/100+doy;
    return era*146097+doe-719468;
}
static void civil(int64_t days, int64_t *y, int64_t *m, int64_t *d){
    int64_t z=days+719468, era=fdiv(z,146097), doe=z-era*146097;
    int64_t yoe=(doe-doe/1460+doe/36524-doe/146096)/365, doy=doe-(365*yoe+yoe/4-yoe/100), mp=(5*doy+2)/153;
    *d=doy-(153*mp+2)/5+1; *m= mp<10 ? mp+3 : mp-9; *y=yoe+era*400+(*m<=2);
}
static Value tm_civil(int argc, Value *argv, TupleObj *kw){            /* civil(days): (year, month, day) - time.py's _civil */
    mod_no_kw("civil",kw); mod_nargs("civil",argc,1,1);
    int64_t y,m,d; civil(mp_index(argv[0],"civil"),&y,&m,&d);
    Value v[3]={v_int(y),v_int(m),v_int(d)};
    return mp_tuple(3,v);
}
/* make(t, off, isdst, zone): the struct_time of time t at UTC offset off - time.py's _make (the class: set_struct()) */
static Value struct_class;                                              /* (time.py keeps it: _ppy_time._struct too) */
static Value tm_set_struct(int argc, Value *argv, TupleObj *kw){
    mod_no_kw("set_struct",kw); mod_nargs("set_struct",argc,1,1);
    if(argv[0].k!=V_OBJ || argv[0].u.o->type!=T_type) mp_raise_t(E_TypeError,"set_struct(): a class");
    struct_class=argv[0];
    return v_none();
}
static Value tm_make(int argc, Value *argv, TupleObj *kw){
    mod_no_kw("make",kw); mod_nargs("make",argc,4,4);
    if(struct_class.k!=V_OBJ) mp_raise_t(E_TypeError,"make(): no set_struct() yet");
    argv--;                                                             /* (the arguments as before: argv[1] the time) */
    int64_t off=mp_index(argv[2],"make"), lt=mp_index(argv[1],"make")+off, days=fdiv(lt,86400), rem=lt-days*86400, y,m,d;
    civil(days,&y,&m,&d);
    Value st=mp_instance(AS_TYPE(struct_class));
    if(st.k!=V_OBJ || st.u.o->type->layout!=LY_INSTANCE) mp_raise_t(E_TypeError,"make(): not a struct_time class");
    DictObj *o=AS_INST(st)->dict;
    mp_dict_reserve(o,11);
    mp_dict_set_s(o,"tm_year",v_int(y)); mp_dict_set_s(o,"tm_mon",v_int(m)); mp_dict_set_s(o,"tm_mday",v_int(d));
    mp_dict_set_s(o,"tm_hour",v_int(rem/3600)); mp_dict_set_s(o,"tm_min",v_int(rem/60%60)); mp_dict_set_s(o,"tm_sec",v_int(rem%60));
    mp_dict_set_s(o,"tm_wday",v_int(((days+3)%7+7)%7)); mp_dict_set_s(o,"tm_yday",v_int(days-days_from_civil(y,1,1)+1));
    mp_dict_set_s(o,"tm_isdst",argv[3]); mp_dict_set_s(o,"tm_zone",argv[4]); mp_dict_set_s(o,"tm_gmtoff",v_int(off));
    return st;
}

/* fields(cls, year, month, day, hour, minute, second, isdst): the struct_time (cls) of a date and time - datetime.py's
   _struct (tm_zone and tm_gmtoff None) */
static Value tm_fields(int argc, Value *argv, TupleObj *kw){
    mod_no_kw("fields",kw); mod_nargs("fields",argc,8,8);
    if(argv[0].k!=V_OBJ || argv[0].u.o->type!=T_type) mp_raise_t(E_TypeError,"fields(): a class first");
    int64_t y=mp_index(argv[1],"fields"), m=mp_index(argv[2],"fields"), d=mp_index(argv[3],"fields"), days=days_from_civil(y,m,d);
    Value st=mp_instance(AS_TYPE(argv[0]));
    if(st.k!=V_OBJ || st.u.o->type->layout!=LY_INSTANCE) mp_raise_t(E_TypeError,"fields(): not a struct_time class");
    DictObj *o=AS_INST(st)->dict;
    mp_dict_reserve(o,11);
    mp_dict_set_s(o,"tm_year",v_int(y)); mp_dict_set_s(o,"tm_mon",v_int(m)); mp_dict_set_s(o,"tm_mday",v_int(d));
    mp_dict_set_s(o,"tm_hour",argv[4]); mp_dict_set_s(o,"tm_min",argv[5]); mp_dict_set_s(o,"tm_sec",argv[6]);
    mp_dict_set_s(o,"tm_wday",v_int(((days+3)%7+7)%7)); mp_dict_set_s(o,"tm_yday",v_int(days-days_from_civil(y,1,1)+1));
    mp_dict_set_s(o,"tm_isdst",argv[7]); mp_dict_set_s(o,"tm_zone",v_none()); mp_dict_set_s(o,"tm_gmtoff",v_none());
    return st;
}

/* ---- strftime(format, t): t a struct_time (checked by time.py); None when format has a directive done
   only there (%U %W %V %G %g %s %z %Z %+ ...), a field is not an int or out of the usual ranges */
static const char *const DAYS[7]={"Mon","Tue","Wed","Thu","Fri","Sat","Sun"};
static const char *const FULL_DAYS[7]={"Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"};
static const char *const MONTHS[12]={"Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"};
static const char *const FULL_MONTHS[12]={"January","February","March","April","May","June","July","August","September","October","November","December"};
typedef struct { int64_t year, mon, mday, hour, min, sec, wday, yday, us; int naive; } Fields;   /* naive: a naive datetime's (%f, %z ...) */
static void put2(SBuf *b, int64_t n){                                  /* time.py's _2 */
    if(n>=0 && n<100){ char t[2]={(char)('0'+n/10),(char)('0'+n%10)}; sb_put(b,t,2); } else sb_printf(b,"%lld",(long long)n);
}
static void putsp2(SBuf *b, int64_t n){ if(n>=0 && n<10) sb_putc(b,' '); sb_printf(b,"%lld",(long long)n); }   /* _sp2 */
static int fmt(SBuf *b, const char *s, int64_t n, const Fields *f);
static int fmtc(SBuf *b, const char *s, const Fields *f){ return fmt(b,s,(int64_t)strlen(s),f); }
static int field(SBuf *b, char c, const Fields *f){
    int64_t wd=((f->wday%7)+7)%7, mon=f->mon?f->mon:1, mday=f->mday?f->mday:1, yday=f->yday?f->yday:1, h12=f->hour%12?f->hour%12:12;
    switch(c){
    case 'Y': if(f->year>=0 && f->year<1000) sb_printf(b,"%04lld",(long long)f->year); else sb_printf(b,"%lld",(long long)f->year); return 1;
    case 'm': put2(b,mon); return 1;
    case 'd': put2(b,mday); return 1;
    case 'H': put2(b,f->hour); return 1;
    case 'M': put2(b,f->min); return 1;
    case 'S': put2(b,f->sec); return 1;
    case 'a': sb_puts(b,DAYS[wd]); return 1;
    case 'A': sb_puts(b,FULL_DAYS[wd]); return 1;
    case 'b': case 'h': sb_puts(b,MONTHS[mon-1]); return 1;
    case 'B': sb_puts(b,FULL_MONTHS[mon-1]); return 1;
    case 'c': return fmtc(b,"%a %b %e %H:%M:%S %Y",f);
    case 'C': put2(b,fdiv(f->year,100)); return 1;
    case 'D': case 'x': return fmtc(b,"%m/%d/%y",f);
    case 'e': putsp2(b,mday); return 1;
    case 'F': return fmtc(b,"%Y-%m-%d",f);
    case 'I': put2(b,h12); return 1;
    case 'j': sb_puts(b,yday<10?"00":yday<100?"0":""); sb_printf(b,"%lld",(long long)yday); return 1;
    case 'k': putsp2(b,f->hour); return 1;
    case 'l': putsp2(b,h12); return 1;
    case 'n': sb_putc(b,'\n'); return 1;
    case 'p': sb_puts(b,f->hour>=12?"PM":"AM"); return 1;
    case 'r': return fmtc(b,"%I:%M:%S %p",f);
    case 'R': return fmtc(b,"%H:%M",f);
    case 't': sb_putc(b,'\t'); return 1;
    case 'T': case 'X': return fmtc(b,"%H:%M:%S",f);
    case 'u': sb_printf(b,"%lld",(long long)(wd+1)); return 1;
    case 'w': sb_printf(b,"%lld",(long long)((wd+1)%7)); return 1;
    case 'y': put2(b,((f->year%100)+100)%100); return 1;
    case 'f': if(!f->naive) return 0; sb_printf(b,"%06lld",(long long)f->us); return 1;
    case 'z': case 'Z': return f->naive;                                   /* (a naive datetime's: nothing) */
    case '%': sb_putc(b,'%'); return 1;
    }
    return 0;
}
static int fmt(SBuf *b, const char *s, int64_t n, const Fields *f){
    int64_t i=0;
    while(i<n){
        const char *p=memchr(s+i,'%',(size_t)(n-i));
        if(!p || p+1>=s+n){ sb_put(b,s+i,n-i); return 1; }               /* (a % at the end stays) */
        sb_put(b,s+i,p-(s+i));
        if(p[1]==':' && f->naive && p+2<s+n && p[2]=='z'){ i=p-s+3; continue; }    /* (%:z of a naive datetime: nothing) */
        if(!field(b,p[1],f)) return 0;
        i=p-s+2;
    }
    return 1;
}
static int get_field(DictObj *d, const char *name, int64_t lo, int64_t hi, int64_t *out){
    Value v;
    if(!mp_dict_get_s(d,name,&v) || v.k!=V_INT || v.u.i<lo || v.u.i>hi) return 0;
    *out=v.u.i; return 1;
}
static Value tm_strftime(int argc, Value *argv, TupleObj *kw){
    mod_no_kw("strftime",kw); mod_nargs("strftime",argc,2,2);
    if(argv[0].k!=V_OBJ || argv[0].u.o->type!=T_str || argv[1].k!=V_OBJ || argv[1].u.o->type->layout!=LY_INSTANCE) return v_none();
    DictObj *d=AS_INST(argv[1])->dict; Fields f;
    if(!get_field(d,"tm_year",-1000000000,1000000000,&f.year) || !get_field(d,"tm_mon",0,12,&f.mon) || !get_field(d,"tm_mday",0,31,&f.mday)
       || !get_field(d,"tm_hour",0,23,&f.hour) || !get_field(d,"tm_min",0,59,&f.min) || !get_field(d,"tm_sec",0,61,&f.sec)
       || !get_field(d,"tm_wday",-1,1000000,&f.wday) || !get_field(d,"tm_yday",0,366,&f.yday)) return v_none();
    f.us=0; f.naive=0;
    StrObj *s=(StrObj*)argv[0].u.o;
    SBuf b={0};
    if(!fmt(&b,s->s,s->len,&f)){ free(b.s); return v_none(); }
    return sb_value(&b);
}

/* strftime_ymd(format, year, month, day, hour, minute, second, microsecond): a naive datetime's (a date's: the
   time 0) - datetime.py's strftime without a struct_time; None as strftime() */
static Value tm_strftime_ymd(int argc, Value *argv, TupleObj *kw){
    mod_no_kw("strftime_ymd",kw); mod_nargs("strftime_ymd",argc,8,8);
    if(argv[0].k!=V_OBJ || argv[0].u.o->type!=T_str) return v_none();
    for(int i=1;i<8;i++) if(argv[i].k!=V_INT) return v_none();
    Fields f={argv[1].u.i,argv[2].u.i,argv[3].u.i,argv[4].u.i,argv[5].u.i,argv[6].u.i,0,0,argv[7].u.i,1};
    if(f.year<1 || f.year>9999 || f.mon<1 || f.mon>12 || f.mday<1 || f.mday>31 || f.hour<0 || f.hour>23 || f.min<0 || f.min>59
       || f.sec<0 || f.sec>59 || f.us<0 || f.us>999999) return v_none();
    int64_t days=days_from_civil(f.year,f.mon,f.mday);
    f.wday=((days+3)%7+7)%7; f.yday=days-days_from_civil(f.year,1,1)+1;
    StrObj *s=(StrObj*)argv[0].u.o;
    SBuf b={0};
    if(!fmt(&b,s->s,s->len,&f)){ free(b.s); return v_none(); }
    return sb_value(&b);
}

/* obj(cls, names, *values): an instance of cls with these fields (no __init__, no __setattr__) - the
   interpreter's datetime from fields worked out by datetime.py */
static Value tm_obj(int argc, Value *argv, TupleObj *kw){
    mod_no_kw("obj",kw);
    if(argc<2 || argv[0].k!=V_OBJ || argv[0].u.o->type!=T_type || !IS(argv[1],T_tuple)) mp_raise_t(E_TypeError,"obj(cls, names, *values)");
    TupleObj *names=(TupleObj*)argv[1].u.o;
    if(names->len!=argc-2) mp_raise_t(E_TypeError,"obj(): as many values as names");
    Value o=mp_instance(AS_TYPE(argv[0]));
    if(o.k!=V_OBJ || o.u.o->type->layout!=LY_INSTANCE) mp_raise_t(E_TypeError,"obj(): not a class of plain instances");
    mp_dict_reserve(AS_INST(o)->dict,names->len);
    for(int64_t i=0;i<names->len;i++) mp_dict_set(AS_INST(o)->dict,names->items[i],argv[i+2]);
    return o;
}

/* datetime_at(cls, names, secs, us, off): obj() of the date and time at secs (since 1970 UTC) + off seconds, us
   microseconds - the interpreter's datetime.now() (names: year ... microsecond, tzinfo, fold) */
static Value tm_datetime_at(int argc, Value *argv, TupleObj *kw){
    mod_no_kw("datetime_at",kw); mod_nargs("datetime_at",argc,5,5);
    if(!IS(argv[1],T_tuple) || ((TupleObj*)argv[1].u.o)->len!=9) mp_raise_t(E_TypeError,"datetime_at(cls, names, secs, us, off)");
    int64_t lt=mp_index(argv[2],"datetime_at")+mp_index(argv[4],"datetime_at"), days=fdiv(lt,86400), rem=lt-days*86400, y,m,d;
    civil(days,&y,&m,&d);
    Value v[11]={argv[0],argv[1],v_int(y),v_int(m),v_int(d),v_int(rem/3600),v_int(rem/60%60),v_int(rem%60),argv[3],v_none(),v_int(0)};
    return tm_obj(11,v,NULL);
}

Value make_ppy_time(void){
    Value m=register_module("_ppy_time");
#if !defined(PPY_KOLIBRI)
    set_fn(m,"time",tm_time); set_fn(m,"time_ns",tm_time_ns); set_fn(m,"monotonic",tm_monotonic); set_fn(m,"monotonic_ns",tm_monotonic_ns);
    set_fn(m,"process_time",tm_process_time); set_fn(m,"process_time_ns",tm_process_time_ns);
    set_fn(m,"thread_time",tm_thread_time); set_fn(m,"thread_time_ns",tm_thread_time_ns); set_fn(m,"clock",tm_clock);
    set_fn(m,"perf_counter",tm_monotonic); set_fn(m,"perf_counter_ns",tm_monotonic_ns);       /* (time.py's: the monotonic clock) */
#endif
    set_fn(m,"civil",tm_civil); set_fn(m,"make",tm_make); set_fn(m,"set_struct",tm_set_struct); set_fn(m,"fields",tm_fields); set_fn(m,"strftime",tm_strftime);
    set_fn(m,"strftime_ymd",tm_strftime_ymd); set_fn(m,"obj",tm_obj); set_fn(m,"datetime_at",tm_datetime_at);
    return m;
}
