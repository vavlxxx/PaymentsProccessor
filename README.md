# PaymentsProcessor

Асинхронный сервис процессинга платежей на базе FastAPI, SQLAlchemy, PostgreSQL и RabbitMQ (FastStream) с реализацией Outbox Pattern, идемпотентности, повторных попыток отправки вебхуков и Dead Letter Queue.

## Структура проекта

```
PaymentsProccessor/
├── .env.docker.example      # Переменные окружения для backend и consumer в Docker
├── .env.postgres.example    # Переменные окружения для PostgreSQL
├── .env.rabbit.example      # Переменные окружения для RabbitMQ
├── .env.pytest.example      # Переменные окружения для запуска тестов
├── docker-compose.yml       # Конфигурация сервисов (postgres, rabbitmq, backend, consumer)
├── Dockerfile               # Multi-stage сборка приложения (Python 3.12-slim, uv)
├── pyproject.toml           # Зависимости и конфигурация проекта
├── pytest.ini               # Конфигурация pytest
├── alembic.ini              # Конфигурация миграций Alembic
└── src/
    ├── api/                 # FastAPI приложение, роуты и зависимости
    ├── broker/              # FastStream consumer, publisher и Outbox Relay
    ├── config.py            # Настройки сервиса (Pydantic Settings)
    ├── db/                  # Подключение к БД и DBManager (Unit of Work)
    ├── migrations/          # Миграции схемы БД (Alembic)
    ├── models/              # Модели SQLAlchemy (PaymentORM, OutboxORM)
    ├── repos/               # Репозитории доступа к данным
    ├── schemas/             # Pydantic-схемы (DTO)
    ├── services/            # Бизнес-логика (PaymentsService)
    ├── tests/               # Тесты (API, Consumer, Relay, Service)
    └── utils/               # Enums и кастомные исключения
```

## Стек технологий

- Python 3.12+
- FastAPI + Pydantic v2
- PostgreSQL 16 + SQLAlchemy 2.0 (asyncpg)
- RabbitMQ + FastStream
- Alembic
- Docker & Docker Compose

## Запуск в Docker

Все переменные окружения преднастроены в публичных `.example` файлах и прокинуты в `docker-compose.yml`.

### Запуск сервисов

```bash
docker compose up -d --build
```

Будут запущены 4 сервиса:
1. `payments_postgres` (порт `6432:5432`)
2. `payments_rabbitmq` (порты `5672` и `15672`)
3. `payments_backend` (порт `8888:8888`, выполняет `alembic upgrade head` и запускает Outbox Relay)
4. `payments_consumer` (фоновый обработчик платежей и вебхуков на FastStream)

### Остановка сервисов

```bash
docker compose down
```

### Просмотр логов

```bash
# Логи бэкенда и Outbox Relay
docker compose logs -f backend

# Логи FastStream consumer
docker compose logs -f consumer
```

## Документация API и мониторинг

- **Swagger UI**: http://localhost:8888/docs
- **RabbitMQ Management**: http://localhost:15672 (логин: `guest`, пароль: `guest`)

Для авторизации в API используется заголовок `X-API-Key: test-secret-api-key-12345`.

## Примеры запросов

### Создание платежа

```bash
curl -X POST "http://localhost:8888/api/v1/payments" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-secret-api-key-12345" \
  -H "Idempotency-Key: order-unique-key-1001" \
  -d '{
    "amount": 499.90,
    "currency": "RUB",
    "description": "Оплата заказа #1001",
    "webhook_url": "https://httpbin.org/post",
    "metadata": {"order_id": 1001}
  }'
```

Ответ (`202 Accepted`):
```json
{
  "payment_id": "14745603-9846-43d5-b10a-a7d396fe1295",
  "status": "pending",
  "created_at": "2026-10-17T06:00:00.000000Z"
}
```

При повторном запросе с тем же `Idempotency-Key` вернется `409 Conflict`.

### Получение статуса платежа

```bash
curl -X GET "http://localhost:8888/api/v1/payments/14745603-9846-43d5-b10a-a7d396fe1295/" \
  -H "X-API-Key: test-secret-api-key-12345"
```

## Запуск тестов

Тесты запускаются изолированно в SQLite in-memory окружении без необходимости поднимать внешние БД и RabbitMQ:

```bash
uv run pytest
```
