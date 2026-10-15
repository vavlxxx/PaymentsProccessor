class ApplicationBaseError(Exception):
    detail: str = "Произошла ошибка в приложении"

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class ObjectNotFoundError(ApplicationBaseError):
    detail = "Объект не найден"


class PaymentNotFoundError(ObjectNotFoundError):
    detail = "Платеж не найден"


class ObjectAlreadyExistsError(ApplicationBaseError):
    detail = "Объект уже существует"


class PaymentAlreadyExistsError(ObjectAlreadyExistsError):
    detail = "Платеж с таким ключом идемпотентности уже существует"


class DBQueryError(ApplicationBaseError):
    detail = "Ошибка запроса к базе данных"


class DBConnectionError(ApplicationBaseError):
    detail = "Ошибка соединения с базой данных"
