# vial-http
Awesome http REST tool for vim

[Templates](doc/tutorial.rst#handle-state-via-templates) in action:
![templates](img/templates.gif)


## Features:

* Intuitive syntax mimics HTTP protocol
* Templates to capture state
* Response and connection times in status line
* Automatic json request body detector
* Automatic json/xml response formatter
* Separate buffers for response body, response headers and request
* DRY
* Support for HTTP basic auth
* Support for ssl client certificates


## Install

vial-http is pathogen friendly and only requires vial to be installed:

    cd ~/.vim/bundle
    git clone https://github.com/baverman/vial.git
    git clone https://github.com/baverman/vial-http.git

or for Plug:

    Plug 'baverman/vial'
    Plug 'baverman/vial-http'

Note: vim should be compiled with python or python3 support.


## Docs

You need following options in your vimrc:

    set hidden
    filetype plugin on

`hidden` must be set because Vial-Http uses non-file temporary offscreen
buffers with response content and without `hidden` they will be empty.

`filetype plugin on` needed for default keymap working.

Keymap:

* `<leader><cr>` executes request line under the cursor
* `<c-k>`/`<c-j>` cycle throw response/request/response headers windows

Commands:

* `:VialHttp` executes request line under the cursor
* `:VialHttpBasicAuth [username]` makes `Authorization` header

[Tutorial](doc/tutorial.rst)
