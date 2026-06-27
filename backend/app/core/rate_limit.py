from slowapi import Limiter
from slowapi.util import get_remote_address


def scoped_rate_limit_key(request) -> str:
    path_params = request.scope.get("path_params", {})
    return (
        path_params.get("practice_slug")
        or path_params.get("token")
        or get_remote_address(request)
    )


limiter = Limiter(key_func=scoped_rate_limit_key, default_limits=[])

