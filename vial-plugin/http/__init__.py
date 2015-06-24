import vial


def init():
    vial.register_command('VialHttp', '.plugin.http')
    vial.register_function('VialHttpBasicAuth()', '.plugin.basic_auth')
