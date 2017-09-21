import uuid
import json
from functools import wraps
from  werkzeug.wrappers import Response

from dswf import App, query_string, form, json_body
from covador import opt, list_schema, item, length

app = App()

def api(*args, **kwargs):
    def decorator(func):
        @wraps(func)
        def inner(request, *args, **kwargs):
            result = func(request, *args, **kwargs)
            if isinstance(result, Response):
                return result
            else:
                return Response(json.dumps(result, ensure_ascii=False), 200, mimetype='application/json')
        return app.route(*args, **kwargs)(inner)

    return decorator


@api('/')
def hello(request):
    return {'result': 'Hello'}


@api('/headers')
def headers(request):
    return {'headers': dict(request.headers), 'cookies': dict(request.cookies)}


@api('/query')
@query_string(q=str, page=opt(int, 1))
def query(request, q, page):
    return {'result': q, 'page': 1, 'headers': dict(request.headers)}


@api('/body', methods=['POST'])
def body(request):
    return {'result': request.get_data()}


@api('/form', methods=['POST'])
@form(p1=str, p2=int)
def post_form(request, p1, p2):
    return {'p1': p1, 'p2': p2}


@api('/json', methods=['POST'])
@json_body(p1=str, p2=int)
def post_form(request, p1, p2):
    return {'p1': p1, 'p2': p2}


@api('/multipart', methods=['POST'])
def post_form(request):
    s = list_schema(p1=str, p2=int)
    data = s(request.form.to_dict(False))
    if 'file' in request.files:
        data['file'] = request.files['file'].read()
    return data


@api('/auth/basic')
def basic_auth(request):
    if not request.authorization:
        @request.after
        def set_auth(response):
            response.www_authenticate.set_basic('Westeros')
            response.status_code = 401
        return {'error': 'auth-required'}

    return {'user': request.authorization.username, 'password': request.authorization.password}


@api('/auth/email')
@form(email=str, password=item(str) | length(3, None))
def email_auth(request, email, password):
    token = '{}:{}'.format(email, password)
    @request.after
    def set_auth(response):
        response.headers['Token'] = token
        response.set_cookie('auth', token)
    return {'token': token}


@api('/whoami')
def whoami(request):
    token = request.headers.get('Authorization-Token') or request.cookies.get('auth')
    if not token:
        @request.after
        def error(response):
            response.status_code = 401
        return {'error': 'auth-required'}

    username, _, _ = token.partition(':')
    return {'user': username}


@api('/order', methods=['POST'])
def create_order(request):
    return {'id': str(uuid.uuid4())}


@api('/order/status')
@query_string(order_id=item(str, src='id'))
def create_order(request, order_id):
    return {'id': order_id, 'status': 'inprogress'}


@api('/order', methods=['DELETE'])
@query_string(order_id=item(str, src='id'))
def create_order(request, order_id):
    return {'result': 'ok', 'msg': 'Order {} deleted'.format(order_id)}
