/* Default host filesystem backend.
   Uses ANSI stdio and preserves normal Unix/Windows relative-path behaviour. */

#include "fs.h"
#include <errno.h>
#include <sys/stat.h>
#if defined(_WIN32)
#include <direct.h>
#endif

const char *ppy_fs_backend_name(void){
    return "host-stdio";
}

char *ppy_fs_backend_read_file(const char *normalized_path,char **error_message){
    return ppy_fs_read_file_stdio_path(normalized_path,error_message);
}

int ppy_fs_backend_write_file(const char *normalized_path,const char *data,size_t len,char **error_message){
    FILE *f=fopen(normalized_path,"wb");
    if(!f || fwrite(data,1,len,f)!=len){
        if(f) fclose(f);
        if(error_message){ size_t n=strlen(normalized_path)+32; *error_message=(char*)xmalloc(n); snprintf(*error_message,n,"cannot write %s",normalized_path); }
        return 1;
    }
    return fclose(f)!=0;
}
int ppy_fs_backend_remove(const char *normalized_path){ return remove(normalized_path); }
int ppy_fs_backend_exists(const char *normalized_path){ FILE *f=fopen(normalized_path,"rb"); if(!f) return 0; fclose(f); return 1; }
int ppy_fs_backend_mkdir(const char *normalized_path){
#if defined(_WIN32)
    if(_mkdir(normalized_path)==0) return 0;
#else
    if(mkdir(normalized_path,0777)==0) return 0;
#endif
    struct stat st;
    return errno==EEXIST && stat(normalized_path,&st)==0 && S_ISDIR(st.st_mode) ? 0 : -1;
}
