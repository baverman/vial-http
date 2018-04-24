if exists("b:current_syntax")
    finish
endif

let b:current_syntax = "vial-http"

syn match vialHttpPath "\v[^ ]+$" contained
syn match vialHttpHeader "\v^[a-zA-Z-]+:"
syn keyword vialHttpVerb GET POST PATCH PUT HEAD DELETE nextgroup=vialHttpPath skipwhite
syn include @json syntax/json.vim
syntax region vialJsonBody start="\v^\{" end="\v\}$" contains=@json
syntax match vialHttpComment "\v#.*$"

hi link vialHttpComment Comment
hi link vialHttpVerb Type
hi link vialHttpPath Constant
hi link vialHttpHeader Statement
hi link vialJsonBody SpecialComment
