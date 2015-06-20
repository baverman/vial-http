if exists("b:current_syntax")
    finish
endif

let b:current_syntax = "vial-http"

syntax match vialHttpComment "\v#.*$"

hi link vialHttpComment Comment
