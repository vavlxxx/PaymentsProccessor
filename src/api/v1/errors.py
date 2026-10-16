from fastapi import HTTPException, status


class ApplicationHTTPError(HTTPException):
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error: str = "INTERNAL_SERVER_ERROR"
    detail: str = "Ошибка на стороне сервера"

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(status_code=self.status_code, detail=self.detail)


class NotFoundHTTPError(ApplicationHTTPError):
    status_code = status.HTTP_404_NOT_FOUND
    error = "NOT_FOUND"
    detail = "Объект не найден"


class PaymentNotFoundHTTPError(ApplicationHTTPError):
    status_code = status.HTTP_404_NOT_FOUND
    error = "PAYMENT_NOT_FOUND"
    detail = "Платеж не найден"


class ObjectAlreadyExistsHTTPError(ApplicationHTTPError):
    status_code = status.HTTP_409_CONFLICT
    error = "OBJECT_ALREADY_EXISTS"
    detail = "Объект уже существует"


class PaymentAlreadyExistsHTTPError(ApplicationHTTPError):
    status_code = status.HTTP_409_CONFLICT
    error = "PAYMENT_ALREADY_EXISTS"
    detail = "Платеж с таким ключом идемпотентности уже существует"


class UnauthorizedHTTPError(ApplicationHTTPError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error = "UNAUTHORIZED"
    detail = "Неверный или отсутствующий API ключ"


class BadRequestHTTPError(ApplicationHTTPError):
    status_code = status.HTTP_400_BAD_REQUEST
    error = "BAD_REQUEST"
    detail = "Некорректный запрос"


class DBQueryHTTPError(ApplicationHTTPError):
    status_code = status.HTTP_400_BAD_REQUEST
    error = "DB_QUERY_ERROR"
    detail = "Ошибка запроса к базе данных"
