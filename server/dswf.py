"""Thin wrapper around Werkzeug because Flask and Bottle
do not play nicely with async uwsgi"""
import json

from werkzeug.wrappers import Request, Response
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import HTTPException, NotFound
from werkzeug.utils import redirect

from covador import ValidationDecorator, schema, list_schema
from covador.utils import merge_dicts, parse_qs
from covador.errors import error_to_json


class AppRequest(Request):
    def after(self, func):
        try:
            handlers = self._after_request_handlers
        except AttributeError:
            handlers = self._after_request_handlers = []

        handlers.append(func)
        return func


class App:
    def __init__(self):
        self._url_map = Map(strict_slashes=False)

    def route(self, rule, **kwargs):
        def decorator(func):
            kwargs['endpoint'] = func
            self._url_map.add(Rule(rule, **kwargs))
            return func
        return decorator

    def _dispatch(self, request):
        adapter = self._url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            return endpoint(request, **values)
        except HTTPException as e:
            return e

    def __call__(self, env, sr):
        request = AppRequest(env)
        response = self._dispatch(request)
        after_handlers = getattr(request, '_after_request_handlers', None)
        if after_handlers:
            for h in after_handlers:
                response = h(response) or response
        return response(env, sr)


def error_handler(ctx):  # pragma: no cover
    return Response(error_to_json(ctx.exception), mimetype='application/json', status=400)


def get_qs(request):
    try:
        return request._covador_qs
    except AttributeError:
        qs = request._covador_qs = parse_qs(request.environ.get('QUERY_STRING', ''))
        return qs


def get_form(request):
    try:
        return request._covador_form
    except AttributeError:
        form = request._covador_form = parse_qs(request.get_data(parse_form_data=False))
        return form


_query_string = lambda request, *_args, **_kwargs: get_qs(request)
_form = lambda request, *_args, **_kwargs: get_form(request)
_params = lambda request, *_args, **_kwargs: merge_dicts(get_qs(request), get_form(request))
_rparams = lambda request, *_args, **kwargs: kwargs
_json = lambda request, *_args, **_kwargs: json.loads(request.get_data(parse_form_data=False))

query_string = ValidationDecorator(_query_string, error_handler, list_schema)
form = ValidationDecorator(_form, error_handler, list_schema)
params = ValidationDecorator(_params, error_handler, list_schema)
rparams = ValidationDecorator(_rparams, error_handler, list_schema)
json_body = ValidationDecorator(_json, error_handler, schema)
