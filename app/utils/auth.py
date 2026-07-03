from functools import wraps

from flask import Response, current_app, request


def requires_basic_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        auth = request.authorization
        expected_user = current_app.config["BASIC_AUTH_USERNAME"]
        expected_pass = current_app.config["BASIC_AUTH_PASSWORD"]
        if not expected_user or not expected_pass:
            return Response("Basic auth is not configured", 500)
        if not auth or auth.username != expected_user or auth.password != expected_pass:
            return Response(
                "Login required",
                401,
                {"WWW-Authenticate": 'Basic realm="Splitwise Mini"'},
            )
        return view(*args, **kwargs)

    return wrapped
