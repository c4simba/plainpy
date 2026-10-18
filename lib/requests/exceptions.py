"""requests' exceptions. RequestException is an OSError; it has the response (and the request) when
there is one. Compiled programs: one base class each - ConnectTimeout is a Timeout (not also a
ConnectionError), MissingSchema / InvalidSchema / InvalidURL / InvalidHeader RequestExceptions (not
also ValueErrors), and JSONDecodeError is json's (what r.json() raises there)."""
import sys
from .models import Response, PreparedRequest

if sys._compiled:
    from _ppy_jsonr import JSONDecodeError            # (what the decoders of r.json() raise)

    class RequestException(OSError):
        """There was an ambiguous exception that occurred while handling your request."""

        def __init__(self, msg: str = "", response: Response | None = None, request: PreparedRequest | None = None) -> None:
            super().__init__(msg)
            self.response = response
            self.request = request
            if request is None and response is not None:
                self.request = response.request
else:
    import json as _json

    class RequestException(OSError):
        """There was an ambiguous exception that occurred while handling your request."""

        def __init__(self, *args, response=None, request=None, **kwargs):
            self.response = response
            self.request = request
            if request is None and response is not None:
                self.request = getattr(response, "request", None)
            super().__init__(*args, **kwargs)


class InvalidJSONError(RequestException):
    """A JSON error occurred."""


if not sys._compiled:
    class JSONDecodeError(InvalidJSONError, _json.JSONDecodeError):
        """Couldn't decode the text into json."""

        def __init__(self, *args, **kwargs):
            _json.JSONDecodeError.__init__(self, *args)
            InvalidJSONError.__init__(self, *self.args, **kwargs)


class HTTPError(RequestException):
    """An HTTP error occurred."""


class ConnectionError(RequestException):
    """A Connection error occurred."""


class ProxyError(ConnectionError):
    """A proxy error occurred."""


class SSLError(ConnectionError):
    """An SSL error occurred."""


class Timeout(RequestException):
    """The request timed out (ConnectTimeout, ReadTimeout)."""


if sys._compiled:
    class ConnectTimeout(Timeout):
        """The request timed out while trying to connect to the remote server."""

    class MissingSchema(RequestException):
        """The URL scheme (e.g. http or https) is missing."""

    class InvalidSchema(RequestException):
        """The URL scheme provided is either invalid or unsupported."""

    class InvalidURL(RequestException):
        """The URL provided was somehow invalid."""

    class InvalidHeader(RequestException):
        """The header value provided was somehow invalid."""

    class StreamConsumedError(RequestException):
        """The content for this response was already consumed."""
else:
    class ConnectTimeout(ConnectionError, Timeout):
        """The request timed out while trying to connect to the remote server."""

    class MissingSchema(RequestException, ValueError):
        """The URL scheme (e.g. http or https) is missing."""

    class InvalidSchema(RequestException, ValueError):
        """The URL scheme provided is either invalid or unsupported."""

    class InvalidURL(RequestException, ValueError):
        """The URL provided was somehow invalid."""

    class InvalidHeader(RequestException, ValueError):
        """The header value provided was somehow invalid."""

    class StreamConsumedError(RequestException, TypeError):
        """The content for this response was already consumed."""


class ReadTimeout(Timeout):
    """The server did not send any data in the allotted amount of time."""


class URLRequired(RequestException):
    """A valid URL is required to make a request."""


class TooManyRedirects(RequestException):
    """Too many redirects."""


class InvalidProxyURL(InvalidURL):
    """The proxy URL provided is invalid."""


class ChunkedEncodingError(RequestException):
    """The server declared chunked encoding but sent an invalid chunk."""


class ContentDecodingError(RequestException):
    """Failed to decode response content."""


class RetryError(RequestException):
    """Custom retries logic failed."""


class UnrewindableBodyError(RequestException):
    """Requests encountered an error when trying to rewind a body."""


class RequestsWarning(Warning):
    """Base warning for Requests."""


class FileModeWarning(RequestsWarning):
    """A file was opened in text mode, but Requests determined its binary length."""


class RequestsDependencyWarning(RequestsWarning):
    """An imported dependency doesn't match the expected version range."""
