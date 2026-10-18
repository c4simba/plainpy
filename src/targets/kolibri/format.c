/* snprintf / vsnprintf of plainpy on KolibriOS. The newlib of the KolibriOS toolchains
   is built without long long in its printf: %lld prints the low half of the number and
   every conversion after it takes the wrong argument (an int64 2**51 printed as 0, a
   traceback's function name read from address 0 - "MENUET02"). These do the integer
   conversions themselves (hh h l ll j z t, the flags, width and precision as C has them),
   %s %c %p too, and give each floating-point one to the C library alone. platform.h
   points snprintf and vsnprintf here. */

#include "targets/platform.h"
#undef snprintf
#undef vsnprintf

typedef struct { char *out; size_t cap, len; } Out;

static void put(Out *o, const char *s, size_t k){
    if(o->len < o->cap){ size_t room=o->cap-o->len; memcpy(o->out+o->len,s,k<room?k:room); }
    o->len+=k;
}
static void pad(Out *o, char c, int k){ char b[16]; memset(b,c,sizeof b); while(k>0){ int m=k<16?k:16; put(o,b,(size_t)m); k-=m; } }

/* an integer conversion: mag the magnitude, neg its sign (d, i) */
static void put_int(Out *o, unsigned long long mag, int neg, char conv, const char *flags, int width, int prec){
    int left=strchr(flags,'-')!=NULL, zero=strchr(flags,'0')!=NULL, alt=strchr(flags,'#')!=NULL;
    int base= conv=='o' ? 8 : (conv=='x' || conv=='X' || conv=='p') ? 16 : 10;
    const char *dig= conv=='X' ? "0123456789ABCDEF" : "0123456789abcdef";
    char num[32]; int n=0;
    while(mag){ num[n++]=dig[mag%(unsigned)base]; mag/=(unsigned)base; }
    if(prec<0 && n==0) num[n++]='0';                       /* (precision 0 and the value 0: no digits, as C) */
    char pre[3]; int np=0;
    if(conv=='d' || conv=='i'){
        if(neg) pre[np++]='-'; else if(strchr(flags,'+')) pre[np++]='+'; else if(strchr(flags,' ')) pre[np++]=' ';
    }
    if((alt && (conv=='x' || conv=='X') && n>0 && !(n==1 && num[0]=='0')) || conv=='p'){ pre[np++]='0'; pre[np++]= conv=='X' ? 'X' : 'x'; }
    int zeros= prec>n ? prec-n : 0;
    if(alt && conv=='o' && zeros==0 && (n==0 || num[n-1]!='0')) zeros=1;
    int body=np+zeros+n, fill= width>body ? width-body : 0;
    if(!left && !(zero && prec<0)) pad(o,' ',fill);
    put(o,pre,(size_t)np);
    if(!left && zero && prec<0) pad(o,'0',fill);
    pad(o,'0',zeros);
    for(int i=n-1;i>=0;i--) put(o,&num[i],1);
    if(left) pad(o,' ',fill);
}

int ppy_vsnprintf(char *out, size_t cap, const char *fmt, va_list ap){
    Out o={out,cap,0};
    const char *p=fmt;
    while(*p){
        if(*p!='%'){ const char *q=p; while(*q && *q!='%') q++; put(&o,p,(size_t)(q-p)); p=q; continue; }
        const char *spec=p++;
        if(*p=='%'){ put(&o,"%",1); p++; continue; }
        char flags[8]; int nf=0;
        while(*p && strchr("-+ #0",*p)){ if(nf<6) flags[nf++]=*p; p++; }
        flags[nf]=0;
        int width=0, prec=-1;
        if(*p=='*'){ width=va_arg(ap,int); p++; if(width<0){ width=-width; if(nf<6){ flags[nf++]='-'; flags[nf]=0; } } }
        else while(*p>='0' && *p<='9') width=width*10+(*p++-'0');
        if(*p=='.'){
            p++; prec=0;
            if(*p=='*'){ prec=va_arg(ap,int); p++; if(prec<0) prec=-1; }
            else while(*p>='0' && *p<='9') prec=prec*10+(*p++-'0');
        }
        int wide=0, narrow=0, longd=0;                         /* wide: a 64-bit integer (ll, j, q); narrow: h 1, hh 2; longd: L */
        for(;;){
            if(*p=='l' && p[1]=='l'){ wide=1; p+=2; }
            else if(*p=='j' || *p=='q'){ wide=1; p++; }
            else if(*p=='h' && p[1]=='h'){ narrow=2; p+=2; }
            else if(*p=='h'){ narrow=1; p++; }
            else if(*p=='l' || *p=='z' || *p=='t'){ p++; }      /* (32 bits here) */
            else if(*p=='L'){ longd=1; p++; }
            else break;
        }
        char conv=*p;
        if(!conv){ put(&o,spec,strlen(spec)); break; }
        p++;
        switch(conv){
        case 'd': case 'i': {
            long long v= wide ? va_arg(ap,long long) : (long long)va_arg(ap,int);
            if(narrow==1) v=(short)v; else if(narrow==2) v=(signed char)v;
            unsigned long long mag= v<0 ? (unsigned long long)0-(unsigned long long)v : (unsigned long long)v;
            put_int(&o,mag,v<0,conv,flags,width,prec);
            break; }
        case 'u': case 'x': case 'X': case 'o': {
            unsigned long long v= wide ? va_arg(ap,unsigned long long) : (unsigned long long)va_arg(ap,unsigned int);
            if(narrow==1) v=(unsigned short)v; else if(narrow==2) v=(unsigned char)v;
            put_int(&o,v,0,conv,flags,width,prec);
            break; }
        case 'p': put_int(&o,(unsigned long long)(uintptr_t)va_arg(ap,void*),0,'p',flags,width,-1); break;
        case 'c': {
            char c=(char)va_arg(ap,int); int left=strchr(flags,'-')!=NULL;
            if(!left) pad(&o,' ',width-1);
            put(&o,&c,1);
            if(left) pad(&o,' ',width-1);
            break; }
        case 's': {
            const char *s=va_arg(ap,const char*); if(!s) s="(null)";
            size_t k=0; while(s[k] && (prec<0 || k<(size_t)prec)) k++;
            int left=strchr(flags,'-')!=NULL, fill= width>(int)k ? width-(int)k : 0;
            if(!left) pad(&o,' ',fill);
            put(&o,s,k);
            if(left) pad(&o,' ',fill);
            break; }
        case 'f': case 'F': case 'e': case 'E': case 'g': case 'G': case 'a': case 'A': {
            double v= longd ? (double)va_arg(ap,long double) : va_arg(ap,double);
            char sub[32]; int m=0;
            sub[m++]='%'; for(int i=0;flags[i];i++) sub[m++]=flags[i];
            if(width>0) m+=snprintf(sub+m,sizeof sub-(size_t)m,"%d",width);
            if(prec>=0) m+=snprintf(sub+m,sizeof sub-(size_t)m,".%d",prec);
            sub[m++]=conv; sub[m]=0;
            char buf[128]; int k=snprintf(buf,sizeof buf,sub,v);
            if(k<0) break;
            if((size_t)k<sizeof buf) put(&o,buf,(size_t)k);
            else { char *big=(char*)malloc((size_t)k+1); snprintf(big,(size_t)k+1,sub,v); put(&o,big,(size_t)k); free(big); }
            break; }
        case 'n': (void)va_arg(ap,int*); break;               /* (nothing written there) */
        default: put(&o,spec,(size_t)(p-spec)); break;         /* (not a conversion: as it is) */
        }
    }
    if(cap) out[o.len<cap ? o.len : cap-1]=0;
    return (int)o.len;
}

int ppy_snprintf(char *out, size_t cap, const char *fmt, ...){
    va_list ap; va_start(ap,fmt);
    int n=ppy_vsnprintf(out,cap,fmt,ap);
    va_end(ap);
    return n;
}
