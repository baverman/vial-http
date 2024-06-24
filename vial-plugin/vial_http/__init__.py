import vial


def init():
    vial.register_command('VialHttp', '.plugin.http')
    vial.register_command('VialHttpCurl', '.plugin.curl')
    vial.register_command('VialHttpBasicAuth', '.plugin.basic_auth_cmd', nargs='?')
    vial.register_function('VialHttpBasicAuth()', '.plugin.basic_auth_func')
    vial.register_function('VialHttpResponse()', '.plugin.get_http_response')
