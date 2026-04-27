class AppError(Exception):
    def __init__(self, *, status_code: int, error_code: str, message: str, detail=None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.detail = detail


def error_response_payload(error: AppError) -> dict:
    return {
        "error_code": error.error_code,
        "message": error.message,
        "detail": error.detail,
    }
