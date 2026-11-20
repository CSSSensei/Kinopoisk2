import json
from typing import Optional


class KinopoiskAPIError(RuntimeError):
    pass


class EpisodeNotFoundError(KinopoiskAPIError):
    pass


class HTTPAPIError(KinopoiskAPIError):
    def __init__(self, operation: str, status_code: int, retry_after: Optional[float] = None):
        self.operation = operation
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(f"{operation}: HTTP {status_code}")


class GraphQLAPIError(KinopoiskAPIError):
    def __init__(self, operation: str, errors: list):
        self.operation = operation
        self.errors = errors
        super().__init__(f"{operation}: {json.dumps(errors, ensure_ascii=False)}")


class ResponseValidationError(KinopoiskAPIError):
    pass
