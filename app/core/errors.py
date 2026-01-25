class AppError(Exception):
    pass

class NotFound(AppError):
    pass

class BadRequest(AppError):
    pass
