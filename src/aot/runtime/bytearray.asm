; ---------------------------------------------------------------- bytearrays
; A bytearray is a list whose elements are bytes (rt_kd_u8: a byte a slot, no
; references): +8 its length, +12 its capacity, +16 the bytes, +20 rt_kd_u8.
; rt_list_new, reserve, push, clear and del_slice serve it as they are; the
; list routines that copy an element at a time move 4 or 8 bytes, so what
; copies bytes has its own routines here - which move them as a block.

;;; code rt_kd_u8 : rt_kd_int rt_sb_int
rt_eq_u8:                       ; eax = &a, edx = &b -> eax = 1 if equal
        movzx   ecx,byte [eax]
        movzx   edx,byte [edx]
        xor     eax,eax
        cmp     ecx,edx
        jne     @f
        inc     eax
@@:     ret
rt_cmp_u8:                      ; eax = &a, edx = &b -> eax = -1, 0, 1
        movzx   ecx,byte [eax]
        movzx   edx,byte [edx]
        xor     eax,eax
        cmp     ecx,edx
        je      @f
        mov     eax,1
        ja      @f
        neg     eax
@@:     ret
rt_hash_u8:                     ; eax = &a -> edx:eax = hash(a): the int's
        movzx   eax,byte [eax]
        xor     edx,edx
        ret
rt_repr_u8:                     ; eax = &a: append it in decimal
        movzx   eax,byte [eax]
        xor     edx,edx
        jmp     rt_sb_int
;;; data rt_kd_u8
align 4
rt_kd_u8        dd 1,0,rt_eq_u8,rt_cmp_u8,rt_hash_u8,rt_repr_u8,rt_tn_int

;;; code rt_kd_bytearray : rt_list_eq_k rt_list_cmp_k rt_hash_no rt_repr_ba
;;; data rt_kd_bytearray
align 4
rt_kd_bytearray dd 4,1,rt_list_eq_k,rt_list_cmp_k,rt_hash_no,rt_repr_ba,rt_tn_bytearray
rt_tn_bytearray db 'bytearray',0

;;; code rt_ba_new : rt_list_new rt_kd_u8
rt_ba_new:                      ; -> eax = new empty bytearray
        mov     eax,rt_kd_u8
        jmp     rt_list_new

;;; code rt_ba_byte : rt_panic_value
rt_ba_byte:                     ; edx:eax = int -> eax = that byte (ValueError outside 0..255; ecx kept)
        test    edx,edx
        jnz     .bad
        cmp     eax,255
        ja      .bad
        ret
.bad:   mov     esi,rt_msg_ba_byte
        jmp     rt_panic_value
;;; data rt_ba_byte
rt_msg_ba_byte  db 'byte must be in range(0, 256)',0

;;; code rt_ba_zeros : rt_ba_new rt_list_reserve rt_panic_value
rt_ba_zeros:                    ; eax = n -> eax = new bytearray of n zero bytes (ValueError when negative)
        test    eax,eax
        js      .neg
        push    ebx
        push    eax
        call    rt_ba_new
        mov     ebx,eax
        mov     ecx,[esp]
        call    rt_list_reserve ; (new memory: zeroed)
        pop     ecx
        mov     [ebx+8],ecx
        mov     eax,ebx
        pop     ebx
        ret
.neg:   mov     esi,rt_msg_ba_negcount
        jmp     rt_panic_value
;;; data rt_ba_zeros
rt_msg_ba_negcount db 'negative count',0

;;; code rt_ba_put : rt_list_reserve
rt_ba_put:                      ; eax = bytearray, esi = address, ecx = count: those bytes appended
        push    ebx edi         ; (not its own bytes: they could move while it grows)
        mov     ebx,eax
        push    ecx
        add     ecx,[ebx+8]
        call    rt_list_reserve
        pop     ecx
        mov     edi,[ebx+16]
        add     edi,[ebx+8]
        add     [ebx+8],ecx
        rep     movsb
        mov     eax,ebx
        pop     edi ebx
        ret

;;; code rt_ba_extend_b : rt_ba_put rt_panic_none
rt_ba_extend_b:                 ; eax = bytearray, edx = bytes: its bytes appended
        test    eax,eax
        jz      rt_panic_none
        test    edx,edx
        jz      rt_panic_none
        push    esi
        lea     esi,[edx+12]
        mov     ecx,[edx+8]
        call    rt_ba_put
        pop     esi
        ret

;;; code rt_ba_extend_ba : rt_list_reserve rt_panic_none
rt_ba_extend_ba:                ; eax = bytearray, edx = bytearray (itself too): its bytes appended
        test    eax,eax
        jz      rt_panic_none
        test    edx,edx
        jz      rt_panic_none
        push    ebx esi edi ebp
        mov     ebx,eax
        mov     esi,edx
        mov     ebp,[esi+8]     ; how many (itself: its length before)
        mov     ecx,[ebx+8]
        add     ecx,ebp
        call    rt_list_reserve
        mov     edi,[ebx+16]
        add     edi,[ebx+8]
        mov     esi,[esi+16]    ; (where its bytes are once it has grown)
        mov     ecx,ebp
        add     [ebx+8],ebp
        rep     movsb
        mov     eax,ebx
        pop     ebp edi esi ebx
        ret

;;; code rt_ba_extend_list : rt_list_push rt_ba_byte rt_panic_none
rt_ba_extend_list:              ; eax = bytearray, edx = list[int]: its values appended (ValueError outside 0..255)
        test    eax,eax
        jz      rt_panic_none
        push    ebx esi edi
        mov     ebx,eax
        mov     esi,edx
        xor     edi,edi
.l:     test    esi,esi
        jz      .out
        cmp     edi,[esi+8]
        jae     .out
        mov     ecx,[esi+16]
        mov     eax,[ecx+edi*8]
        mov     edx,[ecx+edi*8+4]
        call    rt_ba_byte
        push    eax
        mov     eax,ebx
        call    rt_list_push
        pop     ecx
        mov     [eax],cl
        inc     edi
        jmp     .l
.out:   mov     eax,ebx
        pop     edi esi ebx
        ret

;;; code rt_ba_from_bytes : rt_ba_new rt_ba_extend_b
rt_ba_from_bytes:               ; eax = bytes -> eax = new bytearray of its bytes
        push    eax
        call    rt_ba_new
        pop     edx
        jmp     rt_ba_extend_b

;;; code rt_ba_copy : rt_ba_new rt_ba_extend_ba
rt_ba_copy:                     ; eax = bytearray -> eax = new bytearray of its bytes
        push    eax
        call    rt_ba_new
        pop     edx
        jmp     rt_ba_extend_ba

;;; code rt_ba_from_list : rt_ba_new rt_ba_extend_list
rt_ba_from_list:                ; eax = list[int] -> eax = new bytearray of its values (ValueError outside 0..255)
        push    eax
        call    rt_ba_new
        pop     edx
        jmp     rt_ba_extend_list

;;; code rt_bytes_of_ba : rt_bytes_new
rt_bytes_of_ba:                 ; eax = bytearray -> eax = new bytes of its bytes
        push    esi edi
        mov     esi,eax
        mov     eax,[esi+8]
        call    rt_bytes_new
        mov     ecx,[esi+8]
        mov     esi,[esi+16]
        lea     edi,[eax+12]
        rep     movsb
        pop     edi esi
        ret

;;; code rt_ba_list : rt_list_new rt_list_reserve rt_kd_int
rt_ba_list:                     ; eax = bytearray -> eax = new list[int] of its bytes
        push    ebx esi edi
        mov     esi,eax
        mov     eax,rt_kd_int
        call    rt_list_new
        mov     ebx,eax
        mov     ecx,[esi+8]
        call    rt_list_reserve
        mov     ecx,[esi+8]
        mov     [ebx+8],ecx
        mov     edi,[ebx+16]
        mov     esi,[esi+16]
        jecxz   .out
.l:     movzx   eax,byte [esi]
        mov     [edi],eax
        mov     dword [edi+4],0
        inc     esi
        add     edi,8
        dec     ecx
        jnz     .l
.out:   mov     eax,ebx
        pop     edi esi ebx
        ret

;;; code rt_ba_add : rt_ba_byte rt_list_push
rt_ba_add:                      ; edx:eax = int, the bytearray at [esp+4] (the caller's top): appended (ValueError outside 0..255)
        call    rt_ba_byte
        push    eax
        mov     eax,[esp+8]
        call    rt_list_push
        pop     ecx
        mov     [eax],cl
        ret

;;; code rt_ba_at : rt_panic_index
rt_ba_at:                       ; eax = bytearray, edx = index (negative: from the end) -> eax = the byte there
        mov     ecx,[eax+8]
        test    edx,edx
        jns     @f
        add     edx,ecx
@@:     cmp     edx,ecx
        jae     rt_ba_index_error
        mov     eax,[eax+16]
        movzx   eax,byte [eax+edx]
        ret
rt_ba_index_error:
        mov     esi,rt_msg_ba_index
        jmp     rt_index_error
;;; data rt_ba_at
rt_msg_ba_index db 'bytearray index out of range',0

;;; code rt_ba_set : rt_ba_at rt_ba_byte
rt_ba_set:                      ; eax = bytearray, edx = index, [esp+4] = the value (an int): b[index] = value
        mov     ecx,[eax+8]
        test    edx,edx
        jns     @f
        add     edx,ecx
@@:     cmp     edx,ecx
        jae     rt_ba_index_error
        push    eax edx
        mov     eax,[esp+12]
        mov     edx,[esp+16]
        call    rt_ba_byte
        mov     ecx,eax
        pop     edx eax
        mov     eax,[eax+16]
        mov     [eax+edx],cl
        ret

;;; code rt_ba_del : rt_ba_at
rt_ba_del:                      ; eax = bytearray, edx = index: del b[index]
        mov     ecx,[eax+8]
        test    edx,edx
        jns     @f
        add     edx,ecx
@@:     cmp     edx,ecx
        jae     rt_ba_index_error
        push    esi edi
        dec     ecx
        mov     [eax+8],ecx
        sub     ecx,edx         ; the bytes after it, moved down
        mov     edi,[eax+16]
        add     edi,edx
        lea     esi,[edi+1]
        rep     movsb
        pop     edi esi
        ret

;;; code rt_ba_pop : rt_panic_index
rt_ba_pop:                      ; eax = bytearray, edx = index (negative: from the end) -> eax = the byte taken out
        mov     ecx,[eax+8]
        test    ecx,ecx
        jz      .empty
        test    edx,edx
        jns     @f
        add     edx,ecx
@@:     cmp     edx,ecx
        jae     .range
        push    esi edi
        dec     ecx
        mov     [eax+8],ecx
        sub     ecx,edx
        mov     edi,[eax+16]
        add     edi,edx
        movzx   eax,byte [edi]
        lea     esi,[edi+1]
        rep     movsb
        pop     edi esi
        ret
.empty: mov     esi,rt_msg_ba_popempty
        jmp     rt_index_error
.range: mov     esi,rt_msg_ba_poprange
        jmp     rt_index_error
;;; data rt_ba_pop
rt_msg_ba_popempty db 'pop from empty bytearray',0
rt_msg_ba_poprange db 'pop index out of range',0

;;; code rt_ba_insert : rt_list_reserve rt_ba_byte
rt_ba_insert:                   ; eax = bytearray, edx = index, [esp+4] = the value (an int): b.insert(index, value)
        push    ebx esi edi
        mov     ebx,eax
        push    edx
        mov     eax,[esp+20]
        mov     edx,[esp+24]
        call    rt_ba_byte
        pop     edx
        push    eax
        mov     eax,[ebx+8]     ; the place: clamped into 0..length, as list.insert does
        test    edx,edx
        jns     @f
        add     edx,eax
        jns     @f
        xor     edx,edx
@@:     cmp     edx,eax
        jbe     @f
        mov     edx,eax
@@:     push    edx
        lea     ecx,[eax+1]
        mov     eax,ebx
        call    rt_list_reserve
        pop     edx
        mov     ecx,[ebx+8]
        sub     ecx,edx         ; the bytes from there, moved up by one
        mov     esi,[ebx+16]
        add     esi,[ebx+8]
        dec     esi
        lea     edi,[esi+1]
        std
        rep     movsb
        cld
        inc     dword [ebx+8]
        mov     eax,[ebx+16]
        pop     ecx
        mov     [eax+edx],cl
        pop     edi esi ebx
        ret

;;; code rt_ba_find_byte
rt_ba_find_byte:                ; eax = bytearray, edx = a byte -> eax = index of its first one, or -1
        push    edi
        mov     ecx,[eax+8]
        mov     edi,[eax+16]
        push    edi
        mov     eax,edx
        jecxz   .no
        repne   scasb
        jne     .no
        lea     eax,[edi-1]
        sub     eax,[esp]
        pop     edi
        pop     edi
        ret
.no:    or      eax,-1
        pop     edi
        pop     edi
        ret

;;; code rt_ba_remove : rt_ba_find_byte rt_ba_del rt_ba_byte rt_panic_value
rt_ba_remove:                   ; eax = bytearray, edx:ecx = an int: its first byte of that value taken out (ValueError)
        push    ebx
        mov     ebx,eax
        mov     eax,ecx
        call    rt_ba_byte
        mov     edx,eax
        mov     eax,ebx
        call    rt_ba_find_byte
        test    eax,eax
        js      .nf
        mov     edx,eax
        mov     eax,ebx
        call    rt_ba_del
        pop     ebx
        ret
.nf:    mov     esi,rt_msg_ba_notfound
        jmp     rt_panic_value
;;; data rt_ba_remove
rt_msg_ba_notfound db 'value not found in bytearray',0

;;; code rt_ba_reverse
rt_ba_reverse:                  ; eax = bytearray: its bytes reversed in place
        push    esi edi
        mov     ecx,[eax+8]
        cmp     ecx,1
        jbe     .out
        mov     esi,[eax+16]
        lea     edi,[esi+ecx-1]
.l:     cmp     esi,edi
        jae     .out
        mov     al,[esi]
        mov     dl,[edi]
        mov     [esi],dl
        mov     [edi],al
        inc     esi
        dec     edi
        jmp     .l
.out:   pop     edi esi
        ret

;;; code rt_ba_mul : rt_ba_new rt_list_reserve
rt_ba_mul:                      ; eax = bytearray, edx = n -> eax = new bytearray: n times its bytes
        push    ebx esi edi ebp
        mov     ebx,eax
        mov     ebp,edx
        call    rt_ba_new
        push    eax
        test    ebp,ebp
        jle     .out
        mov     ecx,[ebx+8]
        imul    ecx,ebp
        call    rt_list_reserve
        mov     eax,[esp]
        mov     edi,[eax+16]
.l:     mov     esi,[ebx+16]
        mov     ecx,[ebx+8]
        add     [eax+8],ecx
        rep     movsb
        dec     ebp
        jnz     .l
.out:   pop     eax
        pop     ebp edi esi ebx
        ret

;;; code rt_ba_slice : rt_slice_range rt_ba_new rt_list_reserve
rt_ba_slice:                    ; [esp+4] bytearray, lo, hi, step, flags -> eax = new bytearray: b[lo:hi:step]
        push    ebx esi edi ebp
        mov     ebx,[esp+20]
        mov     eax,[ebx+8]
        lea     esi,[esp+24]
        call    rt_slice_range  ; eax = start, edx = step, ecx = count
        push    eax edx ecx     ; [esp] count, [esp+4] step, [esp+8] start
        call    rt_ba_new
        mov     ebp,eax
        mov     ecx,[esp]
        call    rt_list_reserve
        mov     ecx,[esp]
        mov     [ebp+8],ecx
        mov     edi,[ebp+16]
        mov     esi,[ebx+16]
        add     esi,[esp+8]
        mov     edx,[esp+4]
        cmp     edx,1
        jne     .step
        rep     movsb
        jmp     .done
.step:  jecxz   .done
.l:     mov     al,[esi]
        mov     [edi],al
        inc     edi
        add     esi,edx
        dec     ecx
        jnz     .l
.done:  add     esp,12
        mov     eax,ebp
        pop     ebp edi esi ebx
        ret

;;; code rt_ba_set_slice : rt_slice_range rt_list_reserve rt_sb_need rt_sb_cstr rt_sb_int rt_sb_take rt_raise_valerr
rt_ba_set_slice:                ; [esp+4] bytearray, lo, hi, step, flags, bytes: b[lo:hi:step] = those bytes
        push    ebx esi edi ebp
        mov     ebx,[esp+20]
        mov     eax,[ebx+8]
        lea     esi,[esp+24]
        call    rt_slice_range  ; eax = start, edx = step, ecx = count
        mov     ebp,[esp+40]    ; the new bytes
        cmp     edx,1
        jne     .ext
        push    eax             ; [esp] start
        mov     edx,[ebp+8]     ; their length
        sub     edx,ecx         ; what the length changes by
        push    ecx edx         ; [esp] change, [esp+4] count
        mov     ecx,[ebx+8]
        add     ecx,edx
        mov     eax,ebx
        call    rt_list_reserve
        mov     eax,[esp+8]
        add     eax,[esp+4]     ; the old end of the slice: what follows it moves
        mov     ecx,[ebx+8]
        sub     ecx,eax         ; bytes after the slice
        mov     esi,[ebx+16]
        add     esi,eax
        mov     edi,esi
        add     edi,[esp]
        cmp     dword [esp],0
        jle     .down
        add     esi,ecx         ; up: from the end down
        dec     esi
        add     edi,ecx
        dec     edi
        std
        rep     movsb
        cld
        jmp     .moved
.down:  rep     movsb
.moved: mov     eax,[esp]
        add     [ebx+8],eax
        mov     edi,[ebx+16]
        add     edi,[esp+8]
        lea     esi,[ebp+12]
        mov     ecx,[ebp+8]
        rep     movsb
        add     esp,12
        pop     ebp edi esi ebx
        ret
.ext:   cmp     ecx,[ebp+8]     ; with a step: as many bytes as the slice has
        jne     .size
        mov     edi,[ebx+16]
        add     edi,eax
        lea     esi,[ebp+12]
        jecxz   .out
.el:    mov     al,[esi]
        mov     [edi],al
        inc     esi
        add     edi,edx
        dec     ecx
        jnz     .el
.out:   pop     ebp edi esi ebx
        ret
.size:  push    ecx
        push    dword [rt_sb_len]
        mov     eax,rt_s_ba_extsize1
        call    rt_sb_cstr
        mov     eax,[ebp+8]
        xor     edx,edx
        call    rt_sb_int
        mov     eax,rt_s_ba_extsize2
        call    rt_sb_cstr
        mov     eax,[esp+4]
        xor     edx,edx
        call    rt_sb_int
        pop     eax
        call    rt_sb_take
        mov     ecx,eax
        jmp     rt_raise_valerr
;;; data rt_ba_set_slice
rt_s_ba_extsize1 db 'attempt to assign bytes of size ',0
rt_s_ba_extsize2 db ' to extended slice of size ',0

;;; code rt_sb_ba : rt_bytes_of_ba rt_sb_cstr rt_sb_char rt_sb_repr_bytes rt_decref
rt_sb_ba:                       ; eax = bytearray: bytearray(b'...') appended
        push    ebx
        call    rt_bytes_of_ba
        mov     ebx,eax
        mov     eax,rt_s_ba_open
        call    rt_sb_cstr
        mov     eax,ebx
        call    rt_sb_repr_bytes
        mov     al,')'
        call    rt_sb_char
        mov     eax,ebx
        call    rt_decref
        pop     ebx
        ret
;;; data rt_sb_ba
rt_s_ba_open    db 'bytearray(',0

;;; code rt_repr_ba : rt_sb_ba rt_repr_none
rt_repr_ba:                     ; eax = &value (bytearray or None): its repr appended
        mov     eax,[eax]
        test    eax,eax
        jz      rt_repr_none
        jmp     rt_sb_ba
