"""Service-level errors, turned into HTTP responses in main.py."""


class ServiceError(Exception):
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFound(ServiceError):
    status_code = 404


class Forbidden(ServiceError):
    status_code = 403


class Conflict(ServiceError):
    status_code = 409


class Invalid(ServiceError):
    status_code = 422


class TooLarge(ServiceError):
    status_code = 413
