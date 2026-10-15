

from src.models.payments import PaymentORM
from src.repos.base import BaseRepo
from src.schemas.payments import PaymentDTO


class PaymentsRepo(BaseRepo):
    """Репозиторий для работы с сущностью платежей."""

    model = PaymentORM
    schema = PaymentDTO
