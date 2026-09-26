import inspect
import os

from vcr import VCR
from vcr.record_mode import RecordMode


def get_vcr_for_test(test_file: str | None = None) -> VCR:
    """
    Creates a VCR instance configured to save cassettes in the folder
    of the test file that calls it.

    On record, the ``Cookie`` request header is omitted from the saved cassette.
    ``Set-Cookie`` values are replaced with non-secret placeholders (they cannot be
    dropped entirely: VCR reapplies these hooks when loading a cassette, and the
    client still needs synthetic cookie headers for replay).

    :param test_file: Path to the test file (usually ``__file__``).
                      If not provided, it is detected automatically.
    :return: Configured VCR instance
    """
    if test_file is None:
        frame = inspect.currentframe()
        if frame is None:
            raise ValueError(
                "Could not detect the current frame. Pass __file__ explicitly."
            )
        try:
            caller_frame = frame.f_back
            if caller_frame is None:
                raise ValueError(
                    "Could not detect the test file. Pass __file__ explicitly."
                )
            test_file = caller_frame.f_globals.get("__file__")
            if test_file is None:
                raise ValueError(
                    "Could not detect the test file. Pass __file__ explicitly."
                )
        finally:
            del frame

    test_dir = os.path.dirname(os.path.abspath(test_file))
    cassette_dir = os.path.join(test_dir)

    def before_record_request(request):
        if request.headers:
            for header_name in list(request.headers.keys()):
                if header_name.lower() == "cookie":
                    del request.headers[header_name]
                    break
            if "X-Auth-Token" in request.headers:
                request.headers["X-Auth-Token"] = ["<FILTERED_X_AUTH_TOKEN>"]
            auth_key = next(
                (k for k in request.headers if k.lower() == "authorization"),
                None,
            )
            if auth_key:
                request.headers[auth_key] = "Bearer <FILTERED_TOKEN>"

        if request.body:
            body_str = (
                request.body.decode("utf-8")
                if isinstance(request.body, bytes)
                else str(request.body)
            )
            # Add here any secret env vars that could leak into recorded request bodies.
            secrets_to_filter: dict[str, str] = {}
            for env_var, placeholder in secrets_to_filter.items():
                secret = os.getenv(env_var)
                if secret and secret in body_str:
                    body_str = body_str.replace(secret, placeholder)

            request.body = (
                body_str.encode("utf-8")
                if isinstance(request.body, bytes)
                else body_str
            )
        return request

    def before_record_response(response):
        # Must redact rather than delete: ``append`` runs this hook when loading
        # from disk too; removing ``Set-Cookie`` would break replay for flows that
        # read auth cookies from response headers.
        headers = response.get("headers")
        if not headers:
            return response
        set_cookie_key = next(
            (k for k in headers if k.lower() == "set-cookie"),
            None,
        )
        if set_cookie_key:
            filtered_cookies = []
            for cookie in headers[set_cookie_key]:
                if "JSESSIONID=" in cookie:
                    cookie_parts = cookie.split(";")
                    filtered_cookie = "JSESSIONID=FILTERED_JSESSIONID"
                    for part in cookie_parts[1:]:
                        filtered_cookie += f"; {part.strip()}"
                    filtered_cookies.append(filtered_cookie)
                else:
                    filtered_cookies.append(cookie)
            headers[set_cookie_key] = filtered_cookies
        x_auth_key = next(
            (k for k in headers if k.lower() == "x-auth-token"),
            None,
        )
        if x_auth_key:
            headers[x_auth_key] = ["<FILTERED_X_AUTH_TOKEN>"]
        return response

    _mode_raw = (os.getenv("VCR_RECORD_MODE") or "new_episodes").lower().strip()
    try:
        record_mode = RecordMode(_mode_raw)
    except ValueError as e:
        raise ValueError(
            f"Invalid VCR_RECORD_MODE={_mode_raw!r}; expected one of "
            f"{[m.value for m in RecordMode]}"
        ) from e

    return VCR(
        cassette_library_dir=cassette_dir,
        record_mode=record_mode,
        match_on=["uri", "method"],
        filter_post_data_parameters=["password"],
        before_record_request=before_record_request,
        before_record_response=before_record_response,
    )
