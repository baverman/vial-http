# vial-http
Simple http rest tool for vim

Features:

    * Intuitive syntax
    * Response and connection times
    * Automatic json response formatter
    * Separate buffers for response body, response headers and request
    * DRY

[Example session](doc/example.http)

Example binds to cycle between buffers:

    au BufNewFile __vial_http__ nnoremap <buffer> <silent> <c-k> :b __vial_http_req__<cr>
    au BufNewFile __vial_http_req__ nnoremap <buffer> <silent> <c-k> :b __vial_http_hdr__<cr>
    au BufNewFile __vial_http_hdr__ nnoremap <buffer> <silent> <c-k> :b __vial_http__<cr>

![vial-http](img/vial-http.png)
