augroup VialHttpSettings
    au!
    au BufNewFile __vial_http__ nnoremap <buffer> <silent> <c-k> :b __vial_http_req__<cr>
    au BufNewFile __vial_http__ nnoremap <buffer> <silent> <c-j> :b __vial_http_hdr__<cr>
    au BufNewFile __vial_http_req__ nnoremap <buffer> <silent> <c-k> :b __vial_http_hdr__<cr>
    au BufNewFile __vial_http_req__ nnoremap <buffer> <silent> <c-j> :b __vial_http__<cr>
    au BufNewFile __vial_http_hdr__ nnoremap <buffer> <silent> <c-k> :b __vial_http__<cr>
    au BufNewFile __vial_http_hdr__ nnoremap <buffer> <silent> <c-j> :b __vial_http_req__<cr>
augroup END
