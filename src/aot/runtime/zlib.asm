; ---------------------------------------------------------------- zlib
; What zlib.py does in compiled programs (sys._crc32, sys._adler32,
; sys._inflate): the checksums and the decoding of deflate blocks, in the
; runtime instead of a byte - a bit - at a time in Python.

;;; code rt_crc32 : rt_crc32_tab
rt_crc32:                       ; eax = bytes, edx = the CRC so far -> eax = the CRC-32 after its bytes
        push    esi
        not     edx
        mov     ecx,[eax+8]
        lea     esi,[eax+12]
        jecxz   .out
.l:     movzx   eax,byte [esi]
        xor     eax,edx
        and     eax,0xFF
        shr     edx,8
        xor     edx,[rt_crc32_tab+eax*4]
        inc     esi
        dec     ecx
        jnz     .l
.out:   mov     eax,edx
        not     eax
        pop     esi
        ret
;;; data rt_crc32_tab
align 4
rt_crc32_tab:                   ; the CRC of each byte value (polynomial 0xEDB88320)
        dd      0x00000000,0x77073096,0xEE0E612C,0x990951BA,0x076DC419,0x706AF48F,0xE963A535,0x9E6495A3
        dd      0x0EDB8832,0x79DCB8A4,0xE0D5E91E,0x97D2D988,0x09B64C2B,0x7EB17CBD,0xE7B82D07,0x90BF1D91
        dd      0x1DB71064,0x6AB020F2,0xF3B97148,0x84BE41DE,0x1ADAD47D,0x6DDDE4EB,0xF4D4B551,0x83D385C7
        dd      0x136C9856,0x646BA8C0,0xFD62F97A,0x8A65C9EC,0x14015C4F,0x63066CD9,0xFA0F3D63,0x8D080DF5
        dd      0x3B6E20C8,0x4C69105E,0xD56041E4,0xA2677172,0x3C03E4D1,0x4B04D447,0xD20D85FD,0xA50AB56B
        dd      0x35B5A8FA,0x42B2986C,0xDBBBC9D6,0xACBCF940,0x32D86CE3,0x45DF5C75,0xDCD60DCF,0xABD13D59
        dd      0x26D930AC,0x51DE003A,0xC8D75180,0xBFD06116,0x21B4F4B5,0x56B3C423,0xCFBA9599,0xB8BDA50F
        dd      0x2802B89E,0x5F058808,0xC60CD9B2,0xB10BE924,0x2F6F7C87,0x58684C11,0xC1611DAB,0xB6662D3D
        dd      0x76DC4190,0x01DB7106,0x98D220BC,0xEFD5102A,0x71B18589,0x06B6B51F,0x9FBFE4A5,0xE8B8D433
        dd      0x7807C9A2,0x0F00F934,0x9609A88E,0xE10E9818,0x7F6A0DBB,0x086D3D2D,0x91646C97,0xE6635C01
        dd      0x6B6B51F4,0x1C6C6162,0x856530D8,0xF262004E,0x6C0695ED,0x1B01A57B,0x8208F4C1,0xF50FC457
        dd      0x65B0D9C6,0x12B7E950,0x8BBEB8EA,0xFCB9887C,0x62DD1DDF,0x15DA2D49,0x8CD37CF3,0xFBD44C65
        dd      0x4DB26158,0x3AB551CE,0xA3BC0074,0xD4BB30E2,0x4ADFA541,0x3DD895D7,0xA4D1C46D,0xD3D6F4FB
        dd      0x4369E96A,0x346ED9FC,0xAD678846,0xDA60B8D0,0x44042D73,0x33031DE5,0xAA0A4C5F,0xDD0D7CC9
        dd      0x5005713C,0x270241AA,0xBE0B1010,0xC90C2086,0x5768B525,0x206F85B3,0xB966D409,0xCE61E49F
        dd      0x5EDEF90E,0x29D9C998,0xB0D09822,0xC7D7A8B4,0x59B33D17,0x2EB40D81,0xB7BD5C3B,0xC0BA6CAD
        dd      0xEDB88320,0x9ABFB3B6,0x03B6E20C,0x74B1D29A,0xEAD54739,0x9DD277AF,0x04DB2615,0x73DC1683
        dd      0xE3630B12,0x94643B84,0x0D6D6A3E,0x7A6A5AA8,0xE40ECF0B,0x9309FF9D,0x0A00AE27,0x7D079EB1
        dd      0xF00F9344,0x8708A3D2,0x1E01F268,0x6906C2FE,0xF762575D,0x806567CB,0x196C3671,0x6E6B06E7
        dd      0xFED41B76,0x89D32BE0,0x10DA7A5A,0x67DD4ACC,0xF9B9DF6F,0x8EBEEFF9,0x17B7BE43,0x60B08ED5
        dd      0xD6D6A3E8,0xA1D1937E,0x38D8C2C4,0x4FDFF252,0xD1BB67F1,0xA6BC5767,0x3FB506DD,0x48B2364B
        dd      0xD80D2BDA,0xAF0A1B4C,0x36034AF6,0x41047A60,0xDF60EFC3,0xA867DF55,0x316E8EEF,0x4669BE79
        dd      0xCB61B38C,0xBC66831A,0x256FD2A0,0x5268E236,0xCC0C7795,0xBB0B4703,0x220216B9,0x5505262F
        dd      0xC5BA3BBE,0xB2BD0B28,0x2BB45A92,0x5CB36A04,0xC2D7FFA7,0xB5D0CF31,0x2CD99E8B,0x5BDEAE1D
        dd      0x9B64C2B0,0xEC63F226,0x756AA39C,0x026D930A,0x9C0906A9,0xEB0E363F,0x72076785,0x05005713
        dd      0x95BF4A82,0xE2B87A14,0x7BB12BAE,0x0CB61B38,0x92D28E9B,0xE5D5BE0D,0x7CDCEFB7,0x0BDBDF21
        dd      0x86D3D2D4,0xF1D4E242,0x68DDB3F8,0x1FDA836E,0x81BE16CD,0xF6B9265B,0x6FB077E1,0x18B74777
        dd      0x88085AE6,0xFF0F6A70,0x66063BCA,0x11010B5C,0x8F659EFF,0xF862AE69,0x616BFFD3,0x166CCF45
        dd      0xA00AE278,0xD70DD2EE,0x4E048354,0x3903B3C2,0xA7672661,0xD06016F7,0x4969474D,0x3E6E77DB
        dd      0xAED16A4A,0xD9D65ADC,0x40DF0B66,0x37D83BF0,0xA9BCAE53,0xDEBB9EC5,0x47B2CF7F,0x30B5FFE9
        dd      0xBDBDF21C,0xCABAC28A,0x53B39330,0x24B4A3A6,0xBAD03605,0xCDD70693,0x54DE5729,0x23D967BF
        dd      0xB3667A2E,0xC4614AB8,0x5D681B02,0x2A6F2B94,0xB40BBE37,0xC30C8EA1,0x5A05DF1B,0x2D02EF8D

;;; code rt_adler32
rt_adler32:                     ; eax = bytes, edx = the Adler-32 so far -> eax = the Adler-32 after its bytes
        push    ebx esi edi
        lea     esi,[eax+12]
        mov     ecx,[eax+8]
        movzx   edi,dx          ; a
        shr     edx,16
        mov     ebx,edx         ; b
.chunk: test    ecx,ecx
        jz      .done
        mov     eax,ecx         ; 3800 bytes at most between the remainders: b stays within 32 bits
        cmp     eax,3800
        jbe     @f
        mov     eax,3800
@@:     sub     ecx,eax
.l:     movzx   edx,byte [esi]
        inc     esi
        add     edi,edx
        add     ebx,edi
        dec     eax
        jnz     .l
        push    ecx
        mov     ecx,65521
        mov     eax,edi
        xor     edx,edx
        div     ecx
        mov     edi,edx
        mov     eax,ebx
        xor     edx,edx
        div     ecx
        mov     ebx,edx
        pop     ecx
        jmp     .chunk
.done:  mov     eax,ebx
        shl     eax,16
        or      eax,edi
        pop     edi esi ebx
        ret

;;; code rt_inflate : rt_list_reserve rt_inflate_tabs
; One deflate block (RFC 1951) decoded, after Mark Adler's puff.c - as
; src/inflate.c: a canonical Huffman code decoded a bit at a time (its counts
; per length, its symbols in code order), here with the bit buffer in a
; register. The state is a sys.buffer: +0 the position in the input, +4 the
; bits read ahead, +8 how many (fewer than 8 between calls). A block is
; decoded whole or not at all: when the input ends in it, the state and the
; output are as they were (0: more input is wanted). The output is a
; bytearray whose bytes before its end are the window distances reach into.
;
; The frame (ebp-): 4 the state, 8 the input, 12 the output, 16 where the
; input's bytes start, 20 where they end, 28-40 the state and the output's
; length at the block's start, 44 the last block's flag, 48 / 52 the numbers
; of literal/length and distance codes, 116 offs[16] (build), 1332 the
; literal/length code (count[16], symbol[288]: dwords), 1516 the distance
; code (count[16], symbol[30]), 2796 the code lengths (320 dwords).
rt_inflate:                     ; eax = state (buffer), edx = input (bytes), ecx = output (bytearray)
                                ; -> eax = 2 a block decoded, 1 the last one, 0 more input wanted, -1..-8 an error
        push    ebx esi edi ebp
        mov     ebp,esp
        sub     esp,2800
        mov     [ebp-4],eax
        mov     [ebp-8],edx
        mov     [ebp-12],ecx
        lea     ecx,[edx+12]
        mov     [ebp-16],ecx
        add     ecx,[edx+8]
        mov     [ebp-20],ecx
        mov     esi,[eax+12]    ; the position, the bits read ahead
        add     esi,[ebp-16]
        mov     ebx,[eax+16]
        mov     edi,[eax+20]
        mov     [ebp-28],esi
        mov     [ebp-32],ebx
        mov     [ebp-36],edi
        mov     eax,[ebp-12]
        mov     eax,[eax+8]
        mov     [ebp-40],eax
        mov     edx,1
        call    .bits
        mov     [ebp-44],eax
        mov     edx,2
        call    .bits
        test    eax,eax
        jz      .stored
        cmp     eax,1
        je      .fixed
        cmp     eax,2
        je      .dynamic
        mov     eax,-1          ; invalid block type
        jmp     .out

.done:  mov     ecx,edi         ; the block decoded: the whole bytes read ahead given back
        shr     ecx,3
        sub     esi,ecx
        and     edi,7
        mov     ecx,edi
        mov     eax,1
        shl     eax,cl
        dec     eax
        and     ebx,eax
        mov     eax,2
        cmp     dword [ebp-44],0
        je      .out
        mov     eax,1
.out:   mov     edx,[ebp-4]     ; eax = the result: the state kept
        mov     ecx,esi
        sub     ecx,[ebp-16]
        mov     [edx+12],ecx
        mov     [edx+16],ebx
        mov     [edx+20],edi
        mov     esp,ebp
        pop     ebp edi esi ebx
        ret
.short: mov     esi,[ebp-28]    ; the input ended in the block: as at its start
        mov     ebx,[ebp-32]
        mov     edi,[ebp-36]
        mov     eax,[ebp-12]
        mov     ecx,[ebp-40]
        mov     [eax+8],ecx
        xor     eax,eax
        jmp     .out

.bits:                          ; edx = n (0..16) -> eax = the next n bits
        cmp     edi,edx
        jae     .bhave
        cmp     esi,[ebp-20]
        jae     .short
        movzx   eax,byte [esi]
        inc     esi
        mov     ecx,edi
        shl     eax,cl
        or      ebx,eax
        add     edi,8
        jmp     .bits
.bhave: mov     ecx,edx
        mov     eax,1
        shl     eax,cl
        dec     eax
        and     eax,ebx
        shr     ebx,cl
        sub     edi,edx
        ret

.decode:                        ; eax = a code (count[16], symbols) -> eax = the next symbol
.dfill: cmp     edi,16          ; (16 bits ahead, or what the input still has)
        jae     .dgo
        cmp     esi,[ebp-20]
        jae     .dgo
        movzx   edx,byte [esi]
        inc     esi
        mov     ecx,edi
        shl     edx,cl
        or      ebx,edx
        add     edi,8
        jmp     .dfill
.dgo:   push    esi
        lea     edx,[eax+64]
        push    edx             ; [esp] the symbols (where the counts end)
        lea     edx,[eax+4]     ; count[1]
        xor     eax,eax         ; code
        xor     ecx,ecx         ; first
        xor     esi,esi         ; index
.dl:    test    edi,edi
        jz      .short
        dec     edi
        shr     ebx,1
        adc     eax,0           ; code |= the next bit
        add     ecx,[edx]       ; first + count
        cmp     eax,ecx
        jb      .dfound
        add     esi,[edx]       ; index += count
        shl     ecx,1
        shl     eax,1
        add     edx,4
        cmp     edx,[esp]
        jb      .dl
        mov     eax,-3          ; no code of 15 bits or less: invalid code lengths set
        jmp     .out
.dfound:
        sub     eax,ecx         ; symbol[index + code - first]
        add     eax,[edx]
        add     eax,esi
        mov     edx,[esp]
        mov     eax,[edx+eax*4]
        add     esp,4
        pop     esi
        ret

.build:                         ; eax = a code's tables, edx = the code lengths (dwords), ecx = how many
        push    ebx esi edi
        mov     ebx,eax
        mov     esi,edx
        push    ecx
        xor     eax,eax
        mov     edi,ebx
        mov     ecx,16
        rep     stosd           ; count[0..15] = 0
        xor     ecx,ecx
.b1:    cmp     ecx,[esp]
        jae     .b2
        mov     eax,[esi+ecx*4]
        inc     dword [ebx+eax*4]
        inc     ecx
        jmp     .b1
.b2:    mov     dword [ebp-112],0   ; offs[1]
        mov     ecx,1
.b3:    mov     eax,[ebp-116+ecx*4]
        add     eax,[ebx+ecx*4]
        mov     [ebp-112+ecx*4],eax ; offs[len + 1] = offs[len] + count[len]
        inc     ecx
        cmp     ecx,15
        jb      .b3
        xor     ecx,ecx
.b4:    cmp     ecx,[esp]
        jae     .b5
        mov     eax,[esi+ecx*4]
        test    eax,eax
        jz      .b6
        mov     edx,[ebp-116+eax*4]
        mov     [ebx+64+edx*4],ecx  ; symbol[offs[length]++] = sym
        inc     dword [ebp-116+eax*4]
.b6:    inc     ecx
        jmp     .b4
.b5:    pop     ecx
        pop     edi esi ebx
        ret

.stored:
        mov     ecx,edi         ; to a byte boundary: whole bytes read ahead given back
        shr     ecx,3
        sub     esi,ecx
        xor     ebx,ebx
        xor     edi,edi
        mov     eax,[ebp-20]
        sub     eax,esi
        cmp     eax,4
        jb      .short
        movzx   eax,word [esi]
        movzx   ecx,word [esi+2]
        not     ecx
        and     ecx,0xFFFF
        cmp     eax,ecx
        je      @f
        mov     eax,-2          ; invalid stored block lengths
        jmp     .out
@@:     add     esi,4
        mov     ecx,[ebp-20]
        sub     ecx,esi
        cmp     ecx,eax
        jb      .short
        push    eax
        mov     edx,[ebp-12]
        mov     ecx,[edx+8]
        add     ecx,eax
        mov     eax,edx
        call    rt_list_reserve
        pop     ecx
        mov     edx,[ebp-12]
        push    edi
        mov     edi,[edx+16]
        add     edi,[edx+8]
        add     [edx+8],ecx
        rep     movsb
        pop     edi
        jmp     .done

.fixed: lea     edx,[ebp-2796]  ; the fixed codes: 0-143 8 bits, 144-255 9, 256-279 7, 280-287 8; distances 5
        xor     ecx,ecx
.f1:    mov     eax,8
        cmp     ecx,144
        jb      .f2
        mov     eax,9
        cmp     ecx,256
        jb      .f2
        mov     eax,7
        cmp     ecx,280
        jb      .f2
        mov     eax,8
.f2:    mov     [edx+ecx*4],eax
        inc     ecx
        cmp     ecx,288
        jb      .f1
        lea     eax,[ebp-1332]
        mov     ecx,288
        call    .build
        lea     edx,[ebp-2796]
        mov     ecx,30
.f3:    mov     dword [edx+ecx*4-4],5
        dec     ecx
        jnz     .f3
        lea     eax,[ebp-1516]
        mov     ecx,30
        call    .build
        jmp     .codes

.dynamic:
        mov     edx,5
        call    .bits
        add     eax,257
        mov     [ebp-48],eax
        mov     edx,5
        call    .bits
        inc     eax
        mov     [ebp-52],eax
        mov     edx,4
        call    .bits
        add     eax,4
        push    eax             ; how many code length codes
        cmp     dword [ebp-48],286
        ja      .many
        cmp     dword [ebp-52],30
        jbe     @f
.many:  mov     eax,-4          ; too many length or distance symbols
        jmp     .out
@@:     xor     ecx,ecx
.y1:    cmp     ecx,[esp]
        jae     .y2
        push    ecx
        mov     edx,3
        call    .bits
        pop     ecx
        mov     edx,[rt_inflate_order+ecx*4]
        mov     [ebp-2796+edx*4],eax
        inc     ecx
        jmp     .y1
.y2:    cmp     ecx,19
        jae     .y3
        mov     edx,[rt_inflate_order+ecx*4]
        mov     dword [ebp-2796+edx*4],0
        inc     ecx
        jmp     .y2
.y3:    add     esp,4
        lea     eax,[ebp-1332]  ; (the code length code: in the literal/length code's place for now)
        lea     edx,[ebp-2796]
        mov     ecx,19
        call    .build
        xor     ecx,ecx         ; the code lengths of both codes
.y4:    mov     eax,[ebp-48]
        add     eax,[ebp-52]
        cmp     ecx,eax
        jae     .y9
        push    ecx
        lea     eax,[ebp-1332]
        call    .decode
        pop     ecx
        cmp     eax,16
        jae     .yrep
        mov     [ebp-2796+ecx*4],eax
        inc     ecx
        jmp     .y4
.yrep:  push    ecx             ; 16: the last length 3-6 times, 17: zero 3-10, 18: zero 11-138
        cmp     eax,16
        jne     .y17
        test    ecx,ecx
        jz      .badrep
        push    dword [ebp-2796+ecx*4-4]
        mov     edx,2
        call    .bits
        add     eax,3
        jmp     .yput
.y17:   push    0
        cmp     eax,17
        jne     .y18
        mov     edx,3
        call    .bits
        add     eax,3
        jmp     .yput
.y18:   mov     edx,7
        call    .bits
        add     eax,11
.yput:  pop     edx             ; the length
        pop     ecx             ; where
        push    edx
        mov     edx,[ebp-48]
        add     edx,[ebp-52]
        sub     edx,ecx
        cmp     eax,edx
        ja      .badrep
        pop     edx
.yr:    mov     [ebp-2796+ecx*4],edx
        inc     ecx
        dec     eax
        jnz     .yr
        jmp     .y4
.badrep:
        mov     eax,-5          ; invalid bit length repeat
        jmp     .out
.y9:    lea     eax,[ebp-1332]
        lea     edx,[ebp-2796]
        mov     ecx,[ebp-48]
        call    .build
        mov     edx,[ebp-48]
        lea     edx,[ebp-2796+edx*4]
        lea     eax,[ebp-1516]
        mov     ecx,[ebp-52]
        call    .build

.codes: mov     edx,[ebp-12]    ; room for a symbol's bytes (258 at most)
        mov     ecx,[edx+8]
        add     ecx,258
        cmp     ecx,[edx+12]
        jbe     .room
        mov     eax,edx
        call    rt_list_reserve
.room:  lea     eax,[ebp-1332]
        call    .decode
        cmp     eax,256
        jb      .lit
        je      .done
        sub     eax,257
        cmp     eax,29
        jb      @f
        mov     eax,-6          ; invalid literal/length code
        jmp     .out
@@:     mov     ecx,[rt_inflate_lbase+eax*4]
        push    ecx
        mov     edx,[rt_inflate_lext+eax*4]
        call    .bits
        add     [esp],eax       ; the length
        lea     eax,[ebp-1516]
        call    .decode
        cmp     eax,30
        jb      @f
        mov     eax,-7          ; invalid distance code
        jmp     .out
@@:     mov     ecx,[rt_inflate_dbase+eax*4]
        push    ecx
        mov     edx,[rt_inflate_dext+eax*4]
        call    .bits
        add     eax,[esp]       ; the distance
        add     esp,4
        pop     ecx
        mov     edx,[ebp-12]
        cmp     eax,[edx+8]
        jbe     @f
        mov     eax,-8          ; invalid distance too far back
        jmp     .out
@@:     push    esi edi         ; a byte at a time: a run when the distance is shorter than the length
        mov     edi,[edx+16]
        add     edi,[edx+8]
        add     [edx+8],ecx
        mov     esi,edi
        sub     esi,eax
.cp:    mov     al,[esi]
        mov     [edi],al
        inc     esi
        inc     edi
        dec     ecx
        jnz     .cp
        pop     edi esi
        jmp     .codes
.lit:   mov     edx,[ebp-12]
        mov     ecx,[edx+16]
        add     ecx,[edx+8]
        mov     [ecx],al
        inc     dword [edx+8]
        jmp     .codes
;;; data rt_inflate_tabs
align 4
rt_inflate_lbase dd 3,4,5,6,7,8,9,10,11,13,15,17,19,23,27,31,35,43,51,59,67,83,99,115,131,163,195,227,258
rt_inflate_lext  dd 0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2,3,3,3,3,4,4,4,4,5,5,5,5,0
rt_inflate_dbase dd 1,2,3,4,5,7,9,13,17,25,33,49,65,97,129,193,257,385,513,769,1025,1537,2049,3073,4097,6145,8193,12289,16385,24577
rt_inflate_dext  dd 0,0,0,0,1,1,2,2,3,3,4,4,5,5,6,6,7,7,8,8,9,9,10,10,11,11,12,12,13,13
rt_inflate_order dd 16,17,18,0,8,7,9,6,10,5,11,4,12,3,13,2,14,1,15
