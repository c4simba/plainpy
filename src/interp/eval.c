/* ========================= Interpreter: the eval loop =========================
   The loop running a code object's instructions (compile.c emits them). */

#include "run.h"

#define PUSH(v) do{ Value pv_=(v); f->stack[f->sp++]=pv_; }while(0)
#define POP()   (f->stack[--f->sp])
#define TOP()   (f->stack[f->sp-1])
#define SECOND() (f->stack[f->sp-2])
static PPY_NORETURN void unbound_local(CodeObj *co, int i){ raise_name(E_UnboundLocalError,mp_ts->frame,co->varnames[i]->s,"cannot access local variable '%s' where it is not associated with a value",co->varnames[i]->s); }
static Value load_global(Frame *f, StrObj *name){
    Value v;
    if(mp_dict_get(f->globals,v_obj(name),&v)) return v;
    if(mp_dict_get(f->builtins,v_obj(name),&v)) return v;
    raise_name(E_NameError,f,name->s,"name '%s' is not defined",name->s);
}
/* a + b, a * b ... of two ints or floats (an int with a float as num_op does it), done in the loop;
   0: the general way (overflow, a zero divisor, a negative one for // and %, other operators) */
static inline __attribute__((always_inline)) int fast_arith(int op, Value a, Value b, Value *r){
    if(a.k==V_INT && b.k==V_INT){
        int64_t x=a.u.i, y=b.u.i, z;
        switch(op){
            case OP_Add: if(__builtin_add_overflow(x,y,&z)) return 0; break;
            case OP_Sub: if(__builtin_sub_overflow(x,y,&z)) return 0; break;
            case OP_Mult: if(__builtin_mul_overflow(x,y,&z)) return 0; break;
            case OP_FloorDiv: if(y<=0) return 0; z=x/y; if(x%y!=0 && x<0) z--; break;
            case OP_Mod: if(y<=0) return 0; z=x%y; if(z<0) z+=y; break;
            case OP_Div: if(y==0) return 0; *r=v_float((double)x/(double)y); return 1;
            case OP_BitAnd: z=x&y; break;
            case OP_BitOr: z=x|y; break;
            case OP_BitXor: z=x^y; break;
            case OP_RShift: if(y<0 || y>=64) return 0; z=x>>y; break;
            default: return 0;
        }
        *r=v_int(z); return 1;
    }
    if((a.k==V_FLOAT || a.k==V_INT) && (b.k==V_FLOAT || b.k==V_INT)){
        double x= a.k==V_FLOAT ? a.u.f : (double)a.u.i, y= b.k==V_FLOAT ? b.u.f : (double)b.u.i;
        switch(op){
            case OP_Add: *r=v_float(x+y); return 1;
            case OP_Sub: *r=v_float(x-y); return 1;
            case OP_Mult: *r=v_float(x*y); return 1;
            case OP_Div: if(y==0) return 0; *r=v_float(x/y); return 1;
            default: return 0;
        }
    }
    return 0;
}
/* a < b ... of two ints or two floats (an int with a float: exactly, the general way); 0: not done */
static inline __attribute__((always_inline)) int fast_cmp(int op, Value a, Value b, int *r){
    if(a.k==V_INT && b.k==V_INT){ int64_t x=a.u.i, y=b.u.i;
        switch(op){ case OP_Lt: *r=x<y; return 1; case OP_LtE: *r=x<=y; return 1; case OP_Gt: *r=x>y; return 1; case OP_GtE: *r=x>=y; return 1;
                    case OP_Eq: *r=x==y; return 1; case OP_NotEq: *r=x!=y; return 1; default: return 0; } }
    if(a.k==V_FLOAT && b.k==V_FLOAT){ double x=a.u.f, y=b.u.f;
        switch(op){ case OP_Lt: *r=x<y; return 1; case OP_LtE: *r=x<=y; return 1; case OP_Gt: *r=x>y; return 1; case OP_GtE: *r=x>=y; return 1;
                    case OP_Eq: *r=x==y; return 1; case OP_NotEq: *r=x!=y; return 1; default: return 0; } }
    if(op==OP_Is || op==OP_IsNot){                        /* (as mp_compare) */
        int same= a.k==b.k && (a.k==V_OBJ ? a.u.o==b.u.o : a.k==V_FLOAT ? a.u.f==b.u.f : a.u.i==b.u.i);
        *r= op==OP_Is ? same : !same; return 1; }
    return 0;
}
/* A LOAD_FAST's / CONST's value v and the instructions after it, done at once when they are numbers:
   TOP op v (the next is BINOP, INPLACE, COMPARE), or v op w (the next loads w, the one after is the
   operator); a comparison's JUMP_IF_FALSE / JUMP_IF_TRUE taken at once, an operation's STORE_FAST
   too. The fast operations raise nothing and make no objects, so where the instructions are does
   not matter for a traceback, and a jump into the middle of them just runs them one by one.
   0: not done - v is pushed the usual way. */
/* o.name / o.name = v of an instance of a class (no class attribute of that name, no attribute hooks):
   its dict's; 0: the general way */
static inline __attribute__((always_inline)) int fast_getattr(Value o, Value nm, Value *r){
    if(o.k!=V_OBJ) return 0;
    Type *t=o.u.o->type;
    if(t->layout!=LY_INSTANCE || !(t->flags&TF_HEAP) || (mp_type_hooks_now(t)&TH_GETATTRIBUTE) || mp_type_lookup(t,nm).k!=V_UNDEF) return 0;
    DictObj *d=((InstObj*)o.u.o)->dict;
    return d && mp_dict_get(d,nm,r);
}
static inline __attribute__((always_inline)) int fast_setattr(Value o, Value nm, Value v){
    if(o.k!=V_OBJ) return 0;
    Type *t=o.u.o->type;
    if(t->layout!=LY_INSTANCE || !(t->flags&TF_HEAP) || (mp_type_hooks_now(t)&TH_SETATTR) || mp_type_lookup(t,nm).k!=V_UNDEF) return 0;
    DictObj *d=((InstObj*)o.u.o)->dict;
    if(!d) return 0;
    mp_dict_set(d,nm,v); return 1;
}
/* f->ip after a STORE_FAST at at-1: a JUMP after it taken at once */
static inline __attribute__((always_inline)) void stored_at(Frame *f, CodeObj *co, int at);
/* c[k] (o SUBSCR) / c[k] = TOP (o STORE_SUBSCR) for the two values loaded: a list's or tuple's item
   by an int in range, a dict's by an int or str key (whose hash raises nothing); a JUMP_IF_* on a
   bool item at once. at: the instruction after it. 0: not done */
static inline __attribute__((always_inline)) int fused_subscr(Frame *f, CodeObj *co, Value c, Value k, int o, int at){
    if(c.k!=V_OBJ) return 0;
    Type *t=c.u.o->type;
    if(o==I_SUBSCR){
        Value r;
        if(k.k==V_INT && (t==T_list || t==T_tuple)){
            int64_t n= t==T_list ? AS_LIST(c)->len : AS_TUPLE(c)->len, i=k.u.i; if(i<0) i+=n;
            if(i<0 || i>=n) return 0;
            r= t==T_list ? AS_LIST(c)->items[i] : AS_TUPLE(c)->items[i]; }
        else if(t==T_dict && (k.k==V_INT || (k.k==V_OBJ && k.u.o->type==T_str))){ if(!mp_dict_get(AS_DICT(c),k,&r)) return 0; }
        else return 0;
        if(r.k==V_BOOL && at<co->ncode){ uint32_t j=co->code[at]; int jo=(int)(j&0xff);
            if(jo==I_JUMP_IF_FALSE || jo==I_JUMP_IF_TRUE){ f->ip= (jo==I_JUMP_IF_FALSE ? !r.u.i : r.u.i) ? (int)(j>>8) : at+1; return 1; } }
        f->stack[f->sp++]=r; f->ip=at; return 1;
    }
    Value v=f->stack[f->sp-1];
    if(t==T_list && k.k==V_INT){ ListObj *l=AS_LIST(c); int64_t i=k.u.i; if(i<0) i+=l->len;
        if(i<0 || i>=l->len) return 0;
        l->items[i]=v; }
    else if(t==T_dict && (k.k==V_INT || (k.k==V_OBJ && k.u.o->type==T_str))) mp_dict_set(AS_DICT(c),k,v);
    else return 0;
    f->sp--; f->ip=at; return 1;
}
static inline __attribute__((always_inline)) int fused_load(Frame *f, CodeObj *co, Value v){
    const uint32_t *code=co->code; int ip=f->ip, n=co->ncode, used;
    if(ip>=n) return 0;
    uint32_t ins=code[ip]; int o=(int)(ins&0xff);
    Value a, b;
    if(o==I_BINOP || o==I_INPLACE || o==I_COMPARE){ a=f->stack[f->sp-1]; b=v; used=1; }
    else if(o==I_LOAD_FAST || o==I_CONST || o==I_NONE){
        if(ip+1>=n) return 0;
        b= o==I_CONST ? co->consts[ins>>8] : o==I_NONE ? v_none() : f->fast[ins>>8];
        if(b.k==V_UNDEF) return 0;
        ins=code[ip+1]; o=(int)(ins&0xff);
        if(o==I_SUBSCR || o==I_STORE_SUBSCR) return fused_subscr(f,co,v,b,o,ip+2);
        if(o!=I_BINOP && o!=I_INPLACE && o!=I_COMPARE) return 0;
        a=v; used=2;
    } else return 0;
    int at=ip+used; Value r;                              /* (at: the instruction after the operator) */
    if(o==I_COMPARE){
        int c; if(!fast_cmp((int)(ins>>8),a,b,&c)) return 0;
        if(at<n){ uint32_t j=code[at]; int jo=(int)(j&0xff);
            if(jo==I_JUMP_IF_FALSE || jo==I_JUMP_IF_TRUE){
                if(used==1) f->sp--;
                f->ip= (jo==I_JUMP_IF_FALSE ? !c : c) ? (int)(j>>8) : at+1;
                return 1; } }
        r=v_bool(c);
    } else {
        if(!fast_arith((int)(ins>>8),a,b,&r)) return 0;
        if(at<n && (code[at]&0xff)==I_STORE_FAST){ if(used==1) f->sp--; f->fast[code[at]>>8]=r; stored_at(f,co,at+1); return 1; }
    }
    if(used==1) f->stack[f->sp-1]=r; else f->stack[f->sp++]=r;
    f->ip=at;
    return 1;
}
/* every 64 loop rounds and calls: a collection when one is due, another thread's turn */
static int eval_ticks;
#define TICK() do{ if(++eval_ticks>=64){ eval_ticks=0; mp_gc_maybe(); \
        if(mp_nthreads>1){ Thread *self_=ts; mp_gil_release(); ppy_thread_yield(); mp_gil_acquire(self_); } } }while(0)
static inline __attribute__((always_inline)) void stored_at(Frame *f, CodeObj *co, int at){
    if(at<co->ncode && (co->code[at]&0xff)==I_JUMP){ int to=(int)(co->code[at]>>8); if(to<at){ Thread *ts=mp_ts; TICK(); (void)ts; } f->ip=to; }
    else f->ip=at;
}
static const char *cellname(CodeObj *co, int i){ return i<co->ncells ? co->cellnames[i]->s : co->freenames[i-co->ncells]->s; }
static Value unpack_list(Value seq, int64_t want, int ex){
    if(IS_TUPLE(seq) || IS_LIST(seq)) return seq;
    Value l=mp_list(0,NULL), it=mp_iter(seq), x;
    while(mp_next(it,&x)){ mp_list_append(l,x); if(!ex && AS_LIST(l)->len>want) break; }
    return l;
}
static int64_t seq_len(Value s){ return IS_TUPLE(s) ? AS_TUPLE(s)->len : AS_LIST(s)->len; }
static Value *seq_items(Value s){ return IS_TUPLE(s) ? AS_TUPLE(s)->items : AS_LIST(s)->items; }
static TupleObj *kwnames_of(DictObj *d, Value *vals, int *n){
    int64_t pos=0; Value k, v; int i=0;
    Value names=mp_tuple(d->used,NULL);
    while(mp_dict_next(d,&pos,&k,&v)){
        if(!IS_STR(k)) mp_raise_t(E_TypeError,"keywords must be strings");
        AS_TUPLE(names)->items[i]=k; vals[i]=v; i++;
    }
    *n=i;
    return AS_TUPLE(names);
}
static Value call_ex(Value fn, Value args, Value kwargs){
    TupleObj *a=AS_TUPLE(args);
    if(kwargs.k==V_UNDEF || AS_DICT(kwargs)->used==0) return mp_call(fn,(int)a->len,a->items,NULL);
    DictObj *d=AS_DICT(kwargs);
    Value all=mp_tuple(a->len+d->used,NULL);
    memcpy(AS_TUPLE(all)->items,a->items,sizeof(Value)*(size_t)a->len);
    int nk; TupleObj *kn=kwnames_of(d,AS_TUPLE(all)->items+a->len,&nk);
    return mp_call(fn,(int)(a->len+nk),AS_TUPLE(all)->items,kn);
}
static Value make_function(Frame *f, int flags){
    Value code=POP();
    FuncObj *fn=(FuncObj*)mp_alloc(T_function,sizeof(FuncObj));
    Value fv=v_obj(fn);
    if(flags&4) fn->closure=AS_TUPLE(POP());
    if(flags&2) fn->kwdefaults=AS_DICT(POP());
    if(flags&1) fn->defaults=AS_TUPLE(POP());
    CodeObj *co=(CodeObj*)code.u.o;
    fn->code=co; fn->globals=f->globals; fn->name=co->name; fn->qualname=co->qualname; fn->doc=co->doc;
    Value m; fn->module= mp_dict_get_s(f->globals,"__name__",&m) ? m : v_none();
    return fv;
}
/* the bases with each non-class one that has __mro_entries__ replaced by what that returns
   (PEP 560, as CPython's update_bases); undefined when there is none */
static Value resolve_bases(Value bases){
    TupleObj *bt=AS_TUPLE(bases); Value out=v_undef();
    for(int64_t i=0;i<bt->len;i++){
        Value b=bt->items[i], m;
        if(IS_TYPE(b) || !mp_getattr_opt(b,mp_intern("__mro_entries__"),&m)){ if(out.k!=V_UNDEF) mp_list_append(out,b); continue; }
        if(out.k==V_UNDEF) out=mp_list(i,bt->items);
        Value r=mp_call1(m,bases);
        if(!IS_TUPLE(r)) mp_raise_t(E_TypeError,"__mro_entries__ must return a tuple");
        for(int64_t j=0;j<AS_TUPLE(r)->len;j++) mp_list_append(out,AS_TUPLE(r)->items[j]);
    }
    return out.k==V_UNDEF ? out : mp_tuple(AS_LIST(out)->len,AS_LIST(out)->items);
}
static Value build_class(Frame *f, int arg){
    Value body=POP();
    int nb=arg&0xffff, haskw=(arg>>16)&1;
    Value kw= haskw ? POP() : v_undef();
    Value bases=mp_tuple(nb,f->stack+f->sp-nb); f->sp-=nb;
    Value name=POP();
    Value orig_bases=resolve_bases(bases);                   /* (PEP 560: Generic[T] -> Generic) */
    if(orig_bases.k!=V_UNDEF){ Value t=bases; bases=orig_bases; orig_bases=t; }
    Value meta=v_undef();                                    /* metaclass=..., the other keywords: for the metaclass / __init_subclass__ */
    Value ckw=mp_dict();
    if(haskw){
        int64_t pos=0; Value k, v;
        while(mp_dict_next(AS_DICT(kw),&pos,&k,&v)){
            if(mp_str_eq_c(k,"metaclass")) meta=v;
            else mp_dict_set(AS_DICT(ckw),k,v);
        }
    }
    int explicit_meta= meta.k!=V_UNDEF;
    if(!explicit_meta) meta=v_obj(T_type);
    if(IS_TYPE(meta)){                                       /* the most derived of it and the bases' metaclasses */
        Type *w=AS_TYPE(meta); TupleObj *bt=AS_TUPLE(bases);
        for(int64_t i=0;i<bt->len;i++){ Type *m=TYPE(bt->items[i]);
            if(mp_is_subtype(w,m)) continue;
            if(mp_is_subtype(m,w)){ w=m; continue; }
            mp_raise_t(E_TypeError,"metaclass conflict: the metaclass of a derived class must be a (non-strict) subclass of the metaclasses of all its bases"); }
        meta=v_obj(w);
    }
    int nkw=0; Value kwv[32]; TupleObj *kwn=NULL;
    if(AS_DICT(ckw)->used){ if(AS_DICT(ckw)->used>32) mp_raise_t(E_TypeError,"too many class keywords"); kwn=kwnames_of(AS_DICT(ckw),kwv,&nkw); }
    Value keepkw= kwn ? mp_tuple(nkw,kwv) : v_none(); (void)keepkw;
    Value ns;
    Value prep= IS_TYPE(meta) && AS_TYPE(meta)!=T_type ? mp_type_lookup_s(AS_TYPE(meta),"__prepare__") : v_undef();
    if(prep.k!=V_UNDEF && !IS(prep,T_native)){
        Value pa[34]; pa[0]=name; pa[1]=bases; for(int i=0;i<nkw;i++) pa[2+i]=kwv[i];
        Value pf= descr_get(prep,v_undef(),AS_TYPE(meta));
        ns=mp_call(pf,2+nkw,pa,kwn);
        if(ns.k!=V_OBJ || ns.u.o->type->layout!=LY_DICT) mp_raise_t(E_TypeError,"%s.__prepare__() must return a mapping, not %s",AS_TYPE(meta)->name->s,mp_type_name(ns));
    } else ns=mp_dict();
    FuncObj *bf=AS_FUNC(body);
    Value cell=call_function(bf,0,NULL,NULL,AS_DICT(ns));
    if(orig_bases.k!=V_UNDEF) mp_setitem(ns,mp_str("__orig_bases__"),orig_bases);
    Value cls;
    if(IS_TYPE(meta) && AS_TYPE(meta)==T_type) cls=mp_make_class_kw(T_type,name,bases,AS_DICT(ns),nkw,kwv,kwn);
    else { Value ca[35]; ca[0]=name; ca[1]=bases; ca[2]=ns; for(int i=0;i<nkw;i++) ca[3+i]=kwv[i];
        cls=mp_call(meta,3+nkw,ca,kwn); }
    if(IS(cell,T_cell)) ((CellObj*)cell.u.o)->v=cls;
    return cls;
}
/* a native the eval loop calls for `with`: the special method of the type, bound */
static void special_pair(Value o, const char *en, const char *ex, const char *proto, Value *enter, Value *exitf){
    Value m=mp_type_lookup_s(TYPE(o),en), x=mp_type_lookup_s(TYPE(o),ex);
    const char *miss = x.k==V_UNDEF ? ex : m.k==V_UNDEF ? en : NULL;
    if(miss) mp_raise_t(E_TypeError,"'%s' object does not support the %s protocol (missed %s method)",mp_type_name(o),proto,miss);
    *enter=descr_get(m,o,TYPE(o)); *exitf=descr_get(x,o,TYPE(o));
}
static Value exc_type_of(Value e){ return v_obj(TYPE(e)); }
static Value exc_tb_of(Value e){ ExcObj *x=AS_EXC(e); return x->tb.k==V_UNDEF?v_none():x->tb; }
static int match_seq_ok(Value v){
    Type *t=TYPE(v);
    if(t->layout==LY_LIST || t->layout==LY_TUPLE || t->layout==LY_RANGE) return 1;
    if(t->layout==LY_STR || t->layout==LY_BYTES || t->layout==LY_DICT) return 0;
    if(t->flags&TF_DUNDERS) return mp_type_lookup_s(t,"__getitem__").k!=V_UNDEF && mp_type_lookup_s(t,"__len__").k!=V_UNDEF && mp_type_lookup_s(t,"keys").k==V_UNDEF;
    return 0;
}

Value eval(Frame *f, Value sent, int resume, int throwing){
    Thread *ts=mp_ts;
    CodeObj *co=f->code;
    f->back=ts->frame; ts->frame=f;
    if(++ts->depth>RECURSION_LIMIT){ ts->depth--; ts->frame=f->back; mp_raise_t(E_RecursionError,"maximum recursion depth exceeded"); }
    f->state=FS_RUNNING;
    f->hbase=ts->nhandled;
    if(f->nsaved){ for(int i=0;i<f->nsaved;i++) ts->handled[ts->nhandled++]=f->saved_exc[i]; f->nsaved=0; }
    if(resume && !throwing && !f->nopush) PUSH(sent);
    f->nopush=0;
    Catch c;
    volatile int pending_throw=throwing;
  arm:
    mp_catch_push(&c);
    if(MP_SETJMP(c.jb)){
        /* an exception reached this frame */
        Value e=ts->exc; ts->exc=v_undef();
        ts->frame=f;
        tb_add(e,f);
        if(f->nblocks>0){
            Block b=f->blocks[--f->nblocks];
            if(f->sp>b.sp) close_loop_gens(f->stack+b.sp,f->sp-b.sp);
            f->sp=b.sp; ts->nhandled=b.hdepth;
            PUSH(e); f->ip=b.handler;
            goto arm;
        }
        ts->nhandled=f->hbase; ts->depth--; ts->frame=f->back; f->back=NULL; f->state=FS_DONE;
        if(f->sp>0){ int n=f->sp; f->sp=0; close_loop_gens(f->stack,n); }
        reraise(e);
    }
    if(pending_throw){ pending_throw=0; Value e=sent; mp_raise(e); }
    TICK();
    for(;;){
        uint32_t ins=co->code[f->ip++];
        int op=(int)(ins&0xff), arg=(int)(ins>>8);
        switch(op){
            case I_NOP: break;
            case I_POP: f->sp--; if(arg) close_loop_gens(f->stack+f->sp,1); break;
            case I_DUP: PUSH(TOP()); break;
            case I_DUP2:{ Value a=SECOND(), b=TOP(); PUSH(a); PUSH(b); break; }
            case I_ROT2:{ Value t=TOP(); TOP()=SECOND(); SECOND()=t; break; }
            case I_ROT3:{ Value t=f->stack[f->sp-1]; f->stack[f->sp-1]=f->stack[f->sp-2]; f->stack[f->sp-2]=f->stack[f->sp-3]; f->stack[f->sp-3]=t; break; }
            case I_ROT4:{ Value t=f->stack[f->sp-1]; f->stack[f->sp-1]=f->stack[f->sp-2]; f->stack[f->sp-2]=f->stack[f->sp-3]; f->stack[f->sp-3]=f->stack[f->sp-4]; f->stack[f->sp-4]=t; break; }
            case I_CONST: if(fused_load(f,co,co->consts[arg])) break; PUSH(co->consts[arg]); break;
            case I_NONE: PUSH(v_none()); break;
            case I_LOAD_FAST:{ Value v=f->fast[arg]; if(v.k==V_UNDEF) unbound_local(co,arg); if(fused_load(f,co,v)) break; PUSH(v); break; }
            case I_STORE_FAST: f->fast[arg]=POP(); stored_at(f,co,f->ip); break;
            case I_DEL_FAST: if(f->fast[arg].k==V_UNDEF) unbound_local(co,arg); f->fast[arg]=v_undef(); break;
            case I_LOAD_DEREF:{ Value v=((CellObj*)f->cells[arg].u.o)->v;
                if(v.k==V_UNDEF){ if(arg<co->ncells) raise_name(E_UnboundLocalError,f,cellname(co,arg),"cannot access local variable '%s' where it is not associated with a value",cellname(co,arg));
                    raise_name(E_NameError,f,cellname(co,arg),"cannot access free variable '%s' where it is not associated with a value in enclosing scope",cellname(co,arg)); }
                PUSH(v); break; }
            case I_STORE_DEREF: ((CellObj*)f->cells[arg].u.o)->v=POP(); break;
            case I_DEL_DEREF: ((CellObj*)f->cells[arg].u.o)->v=v_undef(); break;
            case I_LOAD_CELL: PUSH(f->cells[arg]); break;
            case I_LOAD_CLASSDEREF:{ Value v; const char *n=cellname(co,arg);
                if(f->locals && mp_dict_get(f->locals,mp_intern(n),&v)){ PUSH(v); break; }
                v=((CellObj*)f->cells[arg].u.o)->v;
                if(v.k==V_UNDEF) raise_name(E_NameError,f,n,"cannot access free variable '%s' where it is not associated with a value in enclosing scope",n);
                PUSH(v); break; }
            case I_LOAD_GLOBAL:{
#if !defined(PPY_LOWMEM)
                GCache *gc=co->gcache;                   /* (what it found before, while no globals / builtins dict changed) */
                if(gc){ gc+=arg; if(gc->epoch==mp_globals_epoch && gc->g==f->globals && gc->b==f->builtins){ PUSH(gc->v); break; } }
                Value v=load_global(f,co->names[arg]);
                if(!co->gcache){ co->gcache=(GCache*)xmalloc(sizeof(GCache)*(size_t)co->nnames); memset(co->gcache,0,sizeof(GCache)*(size_t)co->nnames); }
                f->globals->h.flags|=OF_GDICT; f->builtins->h.flags|=OF_GDICT;
                gc=co->gcache+arg; gc->epoch=mp_globals_epoch; gc->g=f->globals; gc->b=f->builtins; gc->v=v;
                PUSH(v);
#else
                PUSH(load_global(f,co->names[arg]));
#endif
                break; }
            case I_STORE_GLOBAL: mp_dict_set(f->globals,v_obj(co->names[arg]),POP()); break;
            case I_DEL_GLOBAL: if(!mp_dict_del(f->globals,v_obj(co->names[arg]))) raise_name(E_NameError,f,co->names[arg]->s,"name '%s' is not defined",co->names[arg]->s); break;
            case I_LOAD_NAME:{ Value v; Value nm=v_obj(co->names[arg]);
                if(f->locals && f->locals->h.type!=T_dict){                /* a class namespace from __prepare__: its __getitem__ */
                    Catch c; volatile int got=0;                         /* (volatile: read after a longjmp) */
                    if(!CATCH_BEGIN(c)){ v=mp_getitem(v_obj(f->locals),nm); got=1; CATCH_END(c); }
                    else { Value e=mp_catch_exc(&c); if(!mp_isinstance(e,E_KeyError)) mp_raise(e); }
                    if(got){ PUSH(v); break; } }
                else if(f->locals && mp_dict_get(f->locals,nm,&v)){ PUSH(v); break; }
                PUSH(load_global(f,co->names[arg])); break; }
            case I_STORE_NAME:
                if(f->locals && f->locals->h.type!=T_dict){ Value v=POP(); mp_setitem(v_obj(f->locals),v_obj(co->names[arg]),v); break; }   /* (its __setitem__) */
                mp_dict_set(f->locals?f->locals:f->globals,v_obj(co->names[arg]),POP()); break;
            case I_DEL_NAME: if(!mp_dict_del(f->locals?f->locals:f->globals,v_obj(co->names[arg]))) raise_name(E_NameError,f,co->names[arg]->s,"name '%s' is not defined",co->names[arg]->s); break;
            case I_LOAD_ATTR:{ Value o=TOP(), nm=v_obj(co->names[arg]), v;
                if(fast_getattr(o,nm,&v)){ TOP()=v; break; }        /* (an instance's own attribute: its dict's) */
                TOP()=mp_getattr(o,nm); break; }
            case I_STORE_ATTR:{ Value o=POP(), v=POP(), nm=v_obj(co->names[arg]);
                if(fast_setattr(o,nm,v)) break;
                mp_setattr(o,nm,v); break; }
            case I_DEL_ATTR:{ Value o=POP(); mp_delattr(o,v_obj(co->names[arg])); break; }
            case I_LOAD_METHOD:{
                Value o=TOP(); Value name=v_obj(co->names[arg]); Type *t=TYPE(o);
                if(t->layout!=LY_TYPE && t->layout!=LY_SUPER && t->layout!=LY_MODULE){
                    Value d=mp_type_lookup(t,name);
                    if(d.k==V_OBJ && ((IS(d,T_function) && !((FuncObj*)d.u.o)->builtin) || (IS(d,T_native) && ((NativeObj*)d.u.o)->is_method && ((NativeObj*)d.u.o)->self.k==V_UNDEF))){
                        DictObj *dict=inst_dict(o); Value shadow;
                        if(!dict || !mp_dict_get(dict,name,&shadow)){ TOP()=d; PUSH(o); break; }
                    }
                }
                TOP()=v_undef(); PUSH(mp_getattr(o,name));
                break; }
            case I_CALL_METHOD:{
                int n=arg&0xffff, haskw=(arg>>16)&1;
                TupleObj *kw= haskw ? AS_TUPLE(POP()) : NULL;
                Value *args=f->stack+f->sp-n;
                Value m=f->stack[f->sp-n-2], self=f->stack[f->sp-n-1];
                Value r;
                if(m.k==V_UNDEF) r=mp_call(self,n,args,kw);
                else if(IS(m,T_function)) r=call_function(AS_FUNC(m),n+1,args-1,kw,NULL);
                else { if(args[-1].k==V_OBJ && args[-1].u.o->type->layout==LY_NUM) args[-1]=mp_unbox(args[-1]);   /* (an int subclass's: its value) */
                    r=((NativeObj*)m.u.o)->fn(n+1,args-1,kw); }
                f->sp-=n+2; PUSH(r); break; }
            case I_SUBSCR:{ Value k=POP(), o=TOP();
                if(o.k==V_OBJ){ Type *t=o.u.o->type;              /* a list's / tuple's item by an int, a dict's: here */
                    if(k.k==V_INT && (t==T_list || t==T_tuple)){
                        int64_t n= t==T_list ? AS_LIST(o)->len : AS_TUPLE(o)->len, i=k.u.i; if(i<0) i+=n;
                        if(i>=0 && i<n){ TOP()= t==T_list ? AS_LIST(o)->items[i] : AS_TUPLE(o)->items[i]; break; } }
                    else if(t==T_dict){ Value v; if(mp_dict_get(AS_DICT(o),k,&v)){ TOP()=v; break; } } }
                TOP()=mp_getitem(o,k); break; }
            case I_STORE_SUBSCR:{ Value k=POP(), o=POP(), v=POP();
                if(o.k==V_OBJ){ Type *t=o.u.o->type;
                    if(t==T_list && k.k==V_INT){ ListObj *l=AS_LIST(o); int64_t i=k.u.i; if(i<0) i+=l->len;
                        if(i>=0 && i<l->len){ l->items[i]=v; break; } }
                    else if(t==T_dict){ mp_dict_set(AS_DICT(o),k,v); break; } }
                mp_setitem(o,k,v); break; }
            case I_DEL_SUBSCR:{ Value k=POP(), o=POP(); mp_delitem(o,k); break; }
            case I_BINOP:{ Value b=POP(), a=TOP(), r;
                if(fast_arith(arg,a,b,&r)){ TOP()=r; break; }
                TOP()=mp_binop(arg,a,b); break; }
            case I_INPLACE:{ Value b=POP(), a=TOP(), r;
                if(fast_arith(arg,a,b,&r)){ TOP()=r; break; }   /* (ints and floats: += is +) */
                TOP()=mp_inplace(arg,a,b); break; }
            case I_UNARY: TOP()=mp_unary(arg,TOP()); break;
            case I_NOT: TOP()=v_bool(!mp_truth(TOP())); break;
            case I_TRUTH: TOP()=v_bool(mp_truth(TOP())); break;
            case I_COMPARE:{ Value b=POP(), a=TOP();
                if(a.k==V_INT && b.k==V_INT){
                    int64_t x=a.u.i, y=b.u.i; int r=-1;
                    switch(arg){ case OP_Lt: r=x<y; break; case OP_LtE: r=x<=y; break; case OP_Gt: r=x>y; break; case OP_GtE: r=x>=y; break; case OP_Eq: r=x==y; break; case OP_NotEq: r=x!=y; break; default: break; }
                    if(r>=0){ TOP()=v_bool(r); break; }
                }
                else if(a.k==V_FLOAT && b.k==V_FLOAT){            /* (an int with a float: compared exactly, the general way) */
                    double x=a.u.f, y=b.u.f; int r=-1;
                    switch(arg){ case OP_Lt: r=x<y; break; case OP_LtE: r=x<=y; break; case OP_Gt: r=x>y; break; case OP_GtE: r=x>=y; break; case OP_Eq: r=x==y; break; case OP_NotEq: r=x!=y; break; default: break; }
                    if(r>=0){ TOP()=v_bool(r); break; }
                }
                TOP()=mp_compare(arg,a,b); break; }
            case I_JUMP: if(arg<f->ip) TICK(); f->ip=arg; break;
            case I_JUMP_IF_FALSE:{ Value v=POP(); if(v.k==V_BOOL ? !v.u.i : !mp_truth(v)){ if(arg<f->ip) TICK(); f->ip=arg; } break; }
            case I_JUMP_IF_TRUE:{ Value v=POP(); if(v.k==V_BOOL ? v.u.i : mp_truth(v)){ if(arg<f->ip) TICK(); f->ip=arg; } break; }
            case I_JUMP_IF_FALSE_KEEP: if(!mp_truth(TOP())) f->ip=arg; break;
            case I_JUMP_IF_TRUE_KEEP: if(mp_truth(TOP())) f->ip=arg; break;
            case I_BUILD_TUPLE:{ Value t=mp_tuple(arg,f->stack+f->sp-arg); f->sp-=arg; PUSH(t); break; }
            case I_BUILD_LIST:{ Value l=mp_list(arg,f->stack+f->sp-arg); f->sp-=arg; PUSH(l); break; }
            case I_BUILD_SET:{ int n=arg&0xFFFF; Value s=mp_set(T_set); for(int i=0;i<n;i++) mp_set_add((SetObj*)s.u.o,f->stack[f->sp-n+i]); f->sp-=n;
                if(arg&0x10000){ Value r=mp_set(T_set); mp_set_merge((SetObj*)r.u.o,(SetObj*)s.u.o); s=r; }   /* constants: CPython builds a frozenset and merges it */
                PUSH(s); break; }
            case I_BUILD_DICT:{ Value d=mp_dict(); int base=f->sp-2*arg; for(int i=0;i<arg;i++) mp_dict_set(AS_DICT(d),f->stack[base+2*i],f->stack[base+2*i+1]); f->sp=base; PUSH(d); break; }
            case I_BUILD_SLICE:{ Value c3= arg==3 ? POP() : v_none(); Value b=POP(), a=POP(); PUSH(mp_slice(a,b,c3)); break; }
            case I_BUILD_STRING:{
                SBuf b={0};
                for(int i=0;i<arg;i++){ Value s=f->stack[f->sp-arg+i]; sb_put(&b,AS_STR(s)->s,AS_STR(s)->len); }
                f->sp-=arg; PUSH(sb_value(&b)); break; }
            case I_LIST_APPEND:{ Value v=POP(); mp_list_append(f->stack[f->sp-arg],v); break; }
            case I_LIST_EXTEND:{ Value it=POP(); Value l=f->stack[f->sp-arg];
                if(IS_LIST(it)||IS_TUPLE(it)){ int64_t n=seq_len(it); Value *items=seq_items(it); for(int64_t i=0;i<n;i++) mp_list_append(l,items[i]); }
                else { Catch cc; Value x, iter;
                    if(!CATCH_BEGIN(cc)){ iter=mp_iter(it); CATCH_END(cc); }
                    else { Value e=mp_catch_exc(&cc); if(mp_isinstance(e,E_TypeError) && !(TYPE(it)->flags&TF_DUNDERS)) mp_raise_t(E_TypeError,"Value after * must be an iterable, not %s",mp_type_name(it)); reraise(e); }
                    while(mp_next(iter,&x)) mp_list_append(l,x); }
                break; }
            case I_SET_ADD:{ Value v=POP(); mp_set_add((SetObj*)f->stack[f->sp-arg].u.o,v); break; }
            case I_SET_UPDATE:{ Value it=POP(), x; SetObj *s=(SetObj*)f->stack[f->sp-arg].u.o;
                if(it.k==V_OBJ && it.u.o->type->layout==LY_SET){ mp_set_merge(s,(SetObj*)it.u.o); break; }    /* CPython's set_update */
                Value iter=mp_iter(it); while(mp_next(iter,&x)) mp_set_add(s,x); break; }
            case I_DICT_SET:{ Value v=POP(), k=POP(); mp_dict_set(AS_DICT(f->stack[f->sp-arg]),k,v); break; }
            case I_DICT_UPDATE:{ Value m=POP(); DictObj *d=AS_DICT(f->stack[f->sp-(arg&0xff)]);
                if(IS_DICT(m) || (m.k==V_OBJ && m.u.o->type->layout==LY_DICT)){ int64_t pos=0; Value k, v;
                    while(mp_dict_next(AS_DICT(m),&pos,&k,&v)){
                        if((arg&0x100) && mp_dict_get(d,k,NULL)){ Value fn=f->stack[f->sp-(arg&0xff)-2]; mp_raise_t(E_TypeError,"%s got multiple values for keyword argument '%s'",IS(fn,T_function)?AS_FUNC(fn)->qualname->s:"function",IS_STR(k)?mp_cstr(k):"?"); }
                        mp_dict_set(d,k,v); } }
                else {
                    Value keys;
                    if(!mp_getattr_opt(m,mp_intern("keys"),&keys)) mp_raise_t(E_TypeError,"'%s' object is not a mapping",mp_type_name(m));
                    Value it=mp_iter(mp_call0(keys)), k;
                    while(mp_next(it,&k)) mp_dict_set(d,k,mp_getitem(m,k));
                }
                break; }
            case I_LIST_TO_TUPLE:{ Value l=TOP(); TOP()=mp_tuple(AS_LIST(l)->len,AS_LIST(l)->items); break; }
            case I_FORMAT:{
                Value spec= (arg&0x100) ? POP() : v_undef();
                Value v=TOP(); int conv=arg&0xff;
                if(conv=='r') v=mp_repr(v);
                else if(conv=='s') v=mp_tostr(v);
                else if(conv=='a'){ Value r=mp_repr(v); StrObj *s=AS_STR(r); SBuf b={0}; int64_t p=0;
                    while(p<s->len){ int64_t st=p; uint32_t cp=(uint32_t)mp_utf8_decode(s->s,s->len,&p); if(cp<0x80) sb_put(&b,s->s+st,p-st); else if(cp<0x100) sb_printf(&b,"\\x%02x",cp); else if(cp<0x10000) sb_printf(&b,"\\u%04x",cp); else sb_printf(&b,"\\U%08x",cp); }
                    v=sb_value(&b); }
                if(spec.k==V_UNDEF && IS(v,T_str)){ TOP()=v; break; }
                TOP()=mp_format(v,spec.k==V_UNDEF?mp_str(""):spec); break; }
            case I_UNPACK:{
                Value seq=POP(), orig=seq;
                if(IS_STR(seq) && !(TYPE(seq)->flags&TF_DUNDERS)) seq=mp_list_of(seq);
                Value l=unpack_list(seq,arg,0);
                int64_t n=seq_len(l);
                if(n<arg) mp_raise_t(E_ValueError,"not enough values to unpack (expected %d, got %lld)",arg,(long long)n);
                if(n>arg){ if(IS_TUPLE(orig)||IS_LIST(orig)||IS_DICT(orig)) mp_raise_t(E_ValueError,"too many values to unpack (expected %d, got %lld)",arg,(long long)n); mp_raise_t(E_ValueError,"too many values to unpack (expected %d)",arg); }
                Value *items=seq_items(l);
                for(int i=arg-1;i>=0;i--) PUSH(items[i]);
                break; }
            case I_UNPACK_EX:{
                int before=arg&0xff, after=arg>>8;
                Value seq=POP();
                Value l=mp_list_of(seq);
                int64_t n=AS_LIST(l)->len;
                if(n<before+after) mp_raise_t(E_ValueError,"not enough values to unpack (expected at least %d, got %lld)",before+after,(long long)n);
                Value *items=AS_LIST(l)->items;
                for(int i=0;i<after;i++) PUSH(items[n-1-i]);
                PUSH(mp_list(n-before-after,items+before));
                for(int i=before-1;i>=0;i--) PUSH(AS_LIST(l)->items[i]);
                break; }
            case I_GET_ITER: TOP()=mp_iter(TOP());
                if(arg && IS(TOP(),T_generator) && ((GenObj*)TOP().u.o)->f && ((GenObj*)TOP().u.o)->f->state==FS_NEW) ((GenObj*)TOP().u.o)->loop_owned=1;
                break;
            case I_FOR_ITER:{
                Value it=TOP(), v;
                if(IS(it,T_iter)){
                    IterObj *io=(IterObj*)it.u.o;
                    uint32_t nx=co->code[f->ip]; int store= (nx&0xff)==I_STORE_FAST;   /* (for x in ...: x set at once) */
                    if(io->kind==IT_RANGE){ if(io->n<=0){ f->sp--; f->ip=arg; break; }
                        Value x=v_int(io->i); io->i+=((RangeObj*)io->src.u.o)->step; io->n--;
                        if(store){ f->fast[nx>>8]=x; f->ip++; } else PUSH(x);
                        break; }
                    if(io->kind==IT_SEQ && IS_LIST(io->src)){ ListObj *l=AS_LIST(io->src); if(io->i>=l->len){ f->sp--; f->ip=arg; break; }
                        Value x=l->items[io->i++];
                        if(store){ f->fast[nx>>8]=x; f->ip++; } else PUSH(x);
                        break; }
                    if((io->kind==IT_ENUM||io->kind==IT_ZIP||io->kind==IT_DICTI) && co->code[f->ip]==(uint32_t)(I_UNPACK|2<<8)){   /* for a, b in ...: no tuple */
                        Value a, b; int r=mp_next2(io,&a,&b);
                        if(!r){ f->sp--; f->ip=arg; break; }
                        if(r>0){ PUSH(b); PUSH(a); f->ip++; break; } }
                }
                if(mp_next(it,&v)) PUSH(v);
                else { f->sp--; f->ip=arg; }
                break; }
            case I_CALL:{
                Value *args=f->stack+f->sp-arg; Value fn=args[-1], r;
                if(IS(fn,T_function)) r=call_function(AS_FUNC(fn),arg,args,NULL,NULL);
                else r=mp_call(fn,arg,args,NULL);
                f->sp-=arg+1; PUSH(r); break; }
            case I_CALL_KW:{
                TupleObj *kw=AS_TUPLE(POP());
                Value *args=f->stack+f->sp-arg; Value fn=args[-1];
                Value r=mp_call(fn,arg,args,kw);
                f->sp-=arg+1; PUSH(r); break; }
            case I_CALL_EX:{
                Value kw= (arg&1) ? POP() : v_undef();
                Value args=POP(); Value fn=TOP();
                TOP()=call_ex(fn,args,kw); break; }
            case I_RETURN:{
                Value r=POP();
                ts->catch=c.prev;
                ts->nhandled=f->hbase; ts->depth--; ts->frame=f->back; f->back=NULL; f->state=FS_DONE;
                return r; }
            case I_MAKE_FUNCTION: PUSH(make_function(f,arg)); break;
            case I_MAKE_CLASS: PUSH(build_class(f,arg)); break;
            case I_IMPORT:{
                TupleObj *spec=AS_TUPLE(co->consts[arg]);
                PUSH(mp_import(mp_cstr(spec->items[0]),f->globals,(int)spec->items[1].u.i,(int)spec->items[2].u.i));
                break; }
            case I_IMPORT_FROM: PUSH(mp_import_from(TOP(),v_obj(co->names[arg]))); break;
            case I_IMPORT_STAR:{
                Value m=POP(); DictObj *src=inst_dict(m); DictObj *dst=f->locals?f->locals:f->globals;
                Value all;
                if(src && mp_dict_get_s(src,"__all__",&all)){ Value it=mp_iter(all), k; while(mp_next(it,&k)) mp_dict_set(dst,k,mp_getattr(m,k)); }
                else if(src){ int64_t pos=0; Value k, v; while(mp_dict_next(src,&pos,&k,&v)) if(IS_STR(k) && mp_cstr(k)[0]!='_') mp_dict_set(dst,k,v); }
                break; }
            case I_SETUP:{ Block *b=&f->blocks[f->nblocks++]; b->handler=arg; b->sp=f->sp; b->hdepth=ts->nhandled; break; }
            case I_POP_BLOCK: f->nblocks--; break;
            case I_RAISE:{
                if(arg==0){
                    if(ts->nhandled<=0) mp_raise_t(E_RuntimeError,"No active exception to reraise");
                    reraise(ts->handled[ts->nhandled-1]);
                }
                Value cause= arg==2 ? POP() : v_undef();
                Value e=instantiate_exc(POP());
                if(arg==2){
                    if(!IS_NONE(cause)){ cause=instantiate_exc(cause); }
                    AS_EXC(e)->cause=cause; AS_EXC(e)->suppress=1;
                }
                AS_EXC(e)->tb_frame=NULL;
                mp_raise(e); }
            case I_RERAISE:{ Value e=POP(); if(ts->nhandled>0) ts->nhandled--; reraise(e); }
            case I_PUSH_EXC: if(ts->nhandled<64) ts->handled[ts->nhandled++]=TOP(); break;
            case I_CALL_INTRINSIC:{                       /* except*: 1 begin, 2 match, 3 a handler raised, 4 end */
                static const char *const steps[]={NULL,"_begin","_match","_raised","_end"};
                Value fn=mp_excgroup(steps[arg]);
                if(arg==1){ TOP()=mp_call1(fn,TOP()); break; }
                if(arg==2){ Value t=POP(); Value m=mp_call2(fn,TOP(),t); PUSH(m); break; }
                if(arg==3){ Value x=POP(); mp_call2(fn,TOP(),x); break; }
                { Value r=mp_call1(fn,TOP()); if(!IS_NONE(r)){ f->sp--; if(ts->nhandled>f->hbase) ts->nhandled--; reraise(r); } }
                break; }
            case I_POP_EXC: if(ts->nhandled>f->hbase) ts->nhandled--; break;
            case I_EXC_MATCH:{ Value spec=POP(), e=POP(); PUSH(v_bool(mp_exc_matches(e,spec))); break; }
            case I_YIELD:{
                Value v=POP();
                if(!arg && (co->flags&CO_ASYNCGEN)) v=ag_wrap(v);     /* (a value of the async generator, not an await's) */
                /* the exceptions it is handling stay with it */
                int k=ts->nhandled-f->hbase; if(k>8) k=8;
                for(int i=0;i<k;i++) f->saved_exc[i]=ts->handled[f->hbase+i];
                f->nsaved=k;
                ts->catch=c.prev;
                ts->nhandled=f->hbase; ts->depth--; ts->frame=f->back; f->back=NULL; f->state=FS_SUSPENDED;
                return v; }
            case I_GET_YIELD_FROM_ITER:{ Value v=TOP();
                if(IS(v,T_coroutine) && !(co->flags&CO_CORO)) mp_raise_t(E_TypeError,"cannot 'yield from' a coroutine object in a non-coroutine generator");
                if(!IS(v,T_generator) && !IS(v,T_coroutine)) TOP()=mp_iter(v);
                break; }
            case I_GET_AWAITABLE: TOP()=mp_await_iter(TOP()); break;
            case I_SEND:{
                Value v=POP(), recv=TOP(), out;
                if(send_into(recv,v,&out)){ PUSH(out); f->yf=recv; f->yf_exit=arg; }
                else { f->yf=v_undef(); TOP()=out; f->ip=arg; }
                break; }
            case I_GET_AITER:{ Value o=TOP(); Value m=mp_type_lookup_s(TYPE(o),"__aiter__");
                if(m.k==V_UNDEF) mp_raise_t(E_TypeError,"'async for' requires an object with __aiter__ method, got %s",mp_type_name(o));
                TOP()=mp_call1(m,o); break; }
            case I_GET_ANEXT:{ Value o=TOP(); Value m=mp_type_lookup_s(TYPE(o),"__anext__");
                if(m.k==V_UNDEF) mp_raise_t(E_TypeError,"'async for' received an object from __aiter__ that does not implement __anext__: %s",mp_type_name(o));
                PUSH(mp_call1(m,o)); break; }
            case I_END_ASYNC_FOR:{ Value e=POP(); if(!mp_isinstance(e,E_StopAsyncIteration)) reraise(e); f->sp--; break; }
            case I_ASSERT_FAIL:{ Value m= arg ? POP() : v_undef(); mp_raise(m.k==V_UNDEF ? mp_exc_args(E_AssertionError,mp_tuple(0,NULL)) : mp_exc_args(E_AssertionError,mp_tuple(1,&m))); }
            case I_WITH_ENTER:{
                Value ctx=POP();
                Value enter,exitf; special_pair(ctx,"__enter__","__exit__","context manager",&enter,&exitf);
                PUSH(exitf);
                Block *b=&f->blocks[f->nblocks++]; b->handler=arg; b->sp=f->sp; b->hdepth=ts->nhandled;
                PUSH(mp_call0(enter));
                break; }
            case I_ASYNC_WITH_ENTER:{
                Value ctx=POP();
                Value enter,exitf; special_pair(ctx,"__aenter__","__aexit__","asynchronous context manager",&enter,&exitf);
                PUSH(exitf); PUSH(mp_call0(enter));
                break; }
            case I_WITH_EXIT:
                if(arg==0){ Value ex=POP(); Value a[3]={v_none(),v_none(),v_none()}; mp_call(ex,3,a,NULL); }
                else if(arg==1){ Value e=POP(), ex=POP(); Value a[3]={exc_type_of(e),e,exc_tb_of(e)};
                    Value r=mp_call(ex,3,a,NULL);
                    if(ts->nhandled>0) ts->nhandled--;
                    if(!mp_truth(r)) reraise(e); }
                else if(arg==2){ Value e=POP(), ex=POP(); Value a[3]={exc_type_of(e),e,exc_tb_of(e)}; PUSH(e); PUSH(mp_call(ex,3,a,NULL)); }
                else if(arg==3){ Value r=POP(), e=POP(); if(ts->nhandled>0) ts->nhandled--; if(!mp_truth(r)) reraise(e); }
                else { Value ex=POP(); Value a[3]={v_none(),v_none(),v_none()}; PUSH(mp_call(ex,3,a,NULL)); }
                break;
            case I_SETUP_ANNOTATIONS:{ DictObj *d=f->locals?f->locals:f->globals; if(!mp_dict_get_s(d,"__annotations__",NULL)) mp_dict_set_s(d,"__annotations__",mp_dict()); break; }
            case I_MATCH_SEQ:{
                Value s=TOP(); int nmin=arg&0xffff, star=(arg>>16)&1;
                if(!match_seq_ok(s)){ PUSH(v_none()); break; }
                int64_t n=mp_len(s);
                if(star ? n<nmin : n!=nmin){ PUSH(v_none()); break; }
                PUSH(mp_list_of(s)); break; }
            case I_MATCH_MAP:{ Value s=TOP(); Type *t=TYPE(s);
                int ok= t->layout==LY_DICT || ((t->flags&TF_DUNDERS) && mp_type_lookup_s(t,"keys").k!=V_UNDEF && mp_type_lookup_s(t,"__getitem__").k!=V_UNDEF);
                PUSH(v_bool(ok)); break; }
            case I_MATCH_KEYS:{
                Value keys=TOP(), s=SECOND(); TupleObj *k=AS_TUPLE(keys);
                Value vals=mp_tuple(k->len,NULL); int ok=1;
                for(int64_t i=0;i<k->len && ok;i++){
                    if(IS_DICT(s) || TYPE(s)->layout==LY_DICT){ Value v; if(mp_dict_get(AS_DICT(s),k->items[i],&v)) AS_TUPLE(vals)->items[i]=v; else ok=0; }
                    else { Value get=mp_getattr_s(s,"get"); Value miss=mp_list(0,NULL); Value a[2]={k->items[i],miss}; Value v=mp_call(get,2,a,NULL); if(v.k==V_OBJ && v.u.o==miss.u.o) ok=0; else AS_TUPLE(vals)->items[i]=v; }
                }
                PUSH(ok?vals:v_none());
                if(arg){
                    if(!ok) PUSH(v_none());
                    else { Value rest=mp_dict(); Value it=mp_iter(s), x;
                        while(mp_next(it,&x)){ int skip=0; for(int64_t i=0;i<k->len;i++) if(mp_eq(x,k->items[i])) skip=1; if(!skip) mp_dict_set(AS_DICT(rest),x,mp_getitem(s,x)); }
                        PUSH(rest); }
                }
                break; }
            case I_MATCH_CLASS:{
                Value kwn=POP(), cls=POP(), s=POP();
                if(!IS_TYPE(cls)) mp_raise_t(E_TypeError,"called match pattern must be a class");
                Type *t=AS_TYPE(cls);
                if(!mp_isinstance(s,t)){ PUSH(v_none()); break; }
                TupleObj *kn=AS_TUPLE(kwn); int npos=arg;
                Value out=mp_tuple(npos+kn->len,NULL); int ok=1;
                if(npos){
                    Value ma=mp_type_lookup_s(t,"__match_args__");
                    int self_match= t==T_int||t==T_float||t==T_str||t==T_bool||t==T_bytes||t==T_list||t==T_tuple||t==T_dict||t==T_set||t==T_frozenset;
                    if(ma.k==V_UNDEF && self_match){ if(npos>1) mp_raise_t(E_TypeError,"%s() accepts 1 positional sub-pattern (%d given)",t->name->s,npos); AS_TUPLE(out)->items[0]=s; }
                    else {
                        if(ma.k==V_UNDEF || !IS_TUPLE(ma)) mp_raise_t(E_TypeError,"%s() accepts 0 positional sub-patterns (%d given)",t->name->s,npos);
                        if(AS_TUPLE(ma)->len<npos) mp_raise_t(E_TypeError,"%s() accepts %lld positional sub-patterns (%d given)",t->name->s,(long long)AS_TUPLE(ma)->len,npos);
                        for(int i=0;i<npos && ok;i++){ Value v; if(mp_getattr_opt(s,AS_TUPLE(ma)->items[i],&v)) AS_TUPLE(out)->items[i]=v; else ok=0; }
                    }
                }
                for(int64_t i=0;i<kn->len && ok;i++){ Value v; if(mp_getattr_opt(s,kn->items[i],&v)) AS_TUPLE(out)->items[npos+i]=v; else ok=0; }
                PUSH(ok?out:v_none());
                break; }
            default: mp_raise_t(E_SystemError,"bad instruction %d",op);
        }
    }
}

Value mp_run_code(CodeObj *co, DictObj *globals, DictObj *locals){
    Frame *f=frame_new(co,NULL,globals,locals);
    for(int i=0;i<co->ncells;i++) f->cells[i]=mp_cell(v_undef());
    Catch c; Value r;
    if(!CATCH_BEGIN(c)){ r=eval(f,v_undef(),0,0); CATCH_END(c); }
    else { Value e=mp_catch_exc(&c); free(f); reraise(e); }
    free(f);
    return r;
}
