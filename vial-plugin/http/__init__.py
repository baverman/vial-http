import vial


def init():
    vial.register_command('VialHttp', '.plugin.http')
    vial.register_command('VialHttpRequest', '.plugin.show_request')
    vial.register_command('VialHttpResponseBody', '.plugin.show_resp_body')
    vial.register_command('VialHttpResponseHeaders', '.plugin.show_resp_headers')
