# Асинхронный сервис процессинга платежей

Микросервис для асинхронной обработки платежей в полном соответствии с **ТЗ**:
- Прием запросов на оплату через REST API с защитой от дублей (**Idempotency Key**) и аутентификацией (**X-API-Key**).
- Гарантированная публикация событий в брокер через паттерн **Transactional Outbox**.
- Очередь сообщений в RabbitMQ (**`payments.new`**).
- Единый фоновый **Consumer**, выполняющий полный цикл: эмуляция платежного шлюза (2–5 сек, 90% успех, 10% ошибка), обновление статуса в БД и отправка Webhook уведомлений.
- Повторные попытки (**Retry**) с экспоненциальной задержкой и очередь недоставленных сообщений (**Dead Letter Queue** — `payments.dlq`).
- Первичный ключ платежа — **`payment_id`** (UUID) в `PaymentORM` (без лишнего `id`).
- Полный набор автоматических тестов (23 теста).
- Готовое Docker Compose окружение с 4 сервисами: `postgres`, `rabbitmq`, `api`, `consumer`.

---

## 🛠 Стек технологий

- **Язык**: Python 3.12+ / 3.13
- **Web-фреймворк**: FastAPI + Pydantic v2
- **База данных**: PostgreSQL 16
- **ORM**: SQLAlchemy 2.0 (асинхронный режим, asyncpg / aiosqlite для тестов)
- **Миграции**: Alembic
- **Брокер сообщений**: RabbitMQ (FastStream)
- **HTTP-клиент**: HTTPX (с экспоненциальными повторными попытками)
- **Тестирование**: Pytest + Pytest-Asyncio + HTTPX ASGITransport
- **Контейнеризация**: Docker + Docker Compose

---

## 📋 Сущности и модель данных

### 1. Платеж (`payments`) — `PaymentORM` / `PaymentsORM`

Таблица хранит информацию о платежах. Первичным ключом является **`payment_id`**:

| Поле | Тип | Описание |
|---|---|---|
| `payment_id` | `UUID` | Уникальный идентификатор платежа (**Primary Key**) |
| `amount` | `Numeric(12, 2)` | Сумма платежа (CheckConstraint: `amount > 0`) |
| `currency` | `Enum` | Валюта (`RUB`, `USD`, `EUR`) |
| `description` | `Text` | Описание платежа |
| `payment_metadata` | `JSON` | Пользовательские метаданные (в API передается как `metadata`) |
| `status` | `Enum` | Статус (`pending`, `succeeded`, `failed`) |
| `idempotency_key` | `String(255)` | Уникальный ключ идемпотентности (Unique Index) |
| `webhook_url` | `String(2048)` | URL для отправки уведомления о результате обработки |
| `created_at` | `DateTime(tz)` | Дата и время создания платежа |
| `processed_at` | `DateTime(tz)` | Дата и время завершения обработки (null при создании) |

### 2. Outbox (`outbox`) — `OutboxORM`

Таблица для реализации паттерна **Transactional Outbox**:

| Поле | Тип | Описание |
|---|---|---|
| `id` | `Integer` | Идентификатор записи Outbox (Primary Key, autoincrement) |
| `event_id` | `UUID` | Уникальный идентификатор события |
| `topic` | `String(255)` | Очередь назначения (`payments.new`) |
| `event_type` | `String(100)` | Тип события (`PaymentCreated`) |
| `payload` | `JSON` | Тело события (включая `payment_id`, сумму, валюту и т.д.) |
| `status` | `Enum` | Статус публикации (`pending`, `success`, `failed`) |
| `retry_count` | `Integer` | Количество попыток отправки в RabbitMQ |
| `created_at` | `DateTime(tz)` | Время создания события |
| `updated_at` | `DateTime(tz)` | Время последнего обновления |

---

## 🏛 Архитектура решения и гарантии доставки

```
[Client]
   │
   │ 1. POST /api/v1/payments (Headers: X-API-Key, Idempotency-Key)
   ▼
[FastAPI (api)]
   │
   │ 2. Единая транзакция БД
   ├───► INSERT INTO payments (status='pending', payment_id=UUID)
   └───► INSERT INTO outbox (status='pending', topic='payments.new')
   │
   ▼ 3. Ответ клиенту: 202 Accepted {payment_id, status: 'pending', created_at}
   │
[Outbox Relay Loop] (Фоновый процесс)
   │
   │ 4. SELECT * FROM outbox WHERE status='pending' FOR UPDATE SKIP LOCKED
   ├───► Публикация в RabbitMQ (очередь 'payments.new')
   └───► UPDATE outbox SET status='success'
   │
   ▼
[RabbitMQ]
   │
   ▼ 5. Очередь 'payments.new'
[Consumer]
   │
   │ 6. Проверка идемпотентности по БД (если статус != pending — пропуск)
   │ 7. Эмуляция внешнего шлюза: задержка 2-5 сек, 90% успех, 10% ошибка
   │ 8. UPDATE payments SET status='succeeded'/'failed', processed_at=NOW()
   │ 9. Отправка POST webhook на webhook_url (3 попытки с бэкоффом: 1с, 2с, 4с)
   │
   ├── [Успех] ──► message.ack()
   └── [Сбой] ───► message.reject(requeue=False) ──► payments.retry (TTL 5s) ──► payments.new
                                                   └── (после 3 попыток) ──► payments.dlq
```

### Гарантии надежности:
1. **Transactional Outbox**: Запись платежа и событие на отправку создаются строго в одной транзакции PostgreSQL. Даже при аварийном падении сервиса сразу после ответа клиенту событие не потеряется.
2. **Идемпотентность API**: Заголовок `Idempotency-Key` предотвращает повторные списания при дублировании запросов клиентом (возвращается `409 Conflict`).
3. **Идемпотентность Consumer**: Перед эмуляцией шлюза Consumer проверяет текущий статус платежа в БД. Если платеж уже обработан, повторная эмуляция исключена.
4. **Retry & Dead Letter Queue (DLQ)**:
   - **Вебхуки**: При сетевых ошибках или 5xx кодах webhook переотправляется до 3 раз с экспоненциальной задержкой ($1 \times 2^{n-1}$ сек).
   - **Сообщения брокера**: При отклонении сообщения оно перенаправляется через DLX в очередь `payments.retry` с TTL (5000 мс), откуда возвращается в `payments.new`.
   - Если число попыток превышает 3 (`x-death count >= 3`), сообщение направляется в **`payments.dlq`** с сохранением причины ошибки в заголовке `x-dlq-reason`.

---

## 📂 Структура проекта

```
PaymentsProccessor/
├── .env.docker.example      # Переменные окружения для API и Consumer в Docker
├── .env.postgres.example    # Переменные окружения для PostgreSQL
├── .env.rabbit.example      # Переменные окружения для RabbitMQ
├── docker-compose.yml       # Конфигурация 4 сервисов: postgres, rabbitmq, api, consumer
├── Dockerfile               # Multi-stage сборка на базе Python 3.12-slim и uv
├── pyproject.toml           # Зависимости и конфигурация pytest/ruff
├── alembic.ini              # Настройки миграций Alembic
├── src/
│   ├── api/                 # FastAPI роуты, зависимости, схемы ошибок и Swagger-примеров
│   │   ├── main.py          # Приложение FastAPI, lifespan (DB check + Relay), middleware ошибок
│   │   └── v1/              # Эндпоинты версии 1 (payments, auth, headers, db deps)
│   ├── broker/              # RabbitMQ: FastStream consumer, publisher, outbox relay
│   ├── config.py            # Настройки Pydantic Settings с дефолтными значениями
│   ├── db/                  # Async SQLAlchemy Engine, sessionmaker, DBManager (Unit of Work)
│   ├── migrations/          # Миграции Alembic (таблицы payments c payment_id и outbox)
│   ├── models/              # SQLAlchemy модели: PaymentORM (PaymentsORM), OutboxORM, BaseORM
│   ├── repos/               # Репозитории данных: PaymentsRepo, OutboxRepo, BaseRepo
│   ├── schemas/             # Pydantic DTO: PaymentCreateDTO, PaymentResponseDTO, OutboxDTO
│   ├── services/            # Бизнес-логика: PaymentsService
│   ├── tests/               # Набор автоматических тестов (API, Service, Consumer, Relay)
│   └── utils/               # Enums (Currency, PaymentStatus, OutboxStatus) и исключения
```

---

## 🚀 Запуск через Docker Compose

Все сервисы готовы к запуску без ручной настройки секретов — используются преднастроенные `.example` конфигурации.

### Запуск всех 4 сервисов (`postgres`, `rabbitmq`, `api`, `consumer`):

```bash
docker compose up -d --build
```

### Сервисы в составе Docker Compose:
1. **`payments_postgres`** (`postgres:16-alpine`) — порт `6432:5432`
2. **`payments_rabbitmq`** (`rabbitmq:3.11-management-alpine`) — порты `5672` (AMQP) и `15672` (Web UI)
3. **`payments_api`** (FastAPI) — порт `8888:8888` (при старте накатывает миграции `alembic upgrade head` и запускает Outbox Relay)
4. **`payments_consumer`** (FastStream) — фоновый обработчик платежей и вебхуков

### Проверка статуса контейнеров:

```bash
docker compose ps
```

### Остановка контейнеров:

```bash
docker compose down
```

---

## 🧪 Запуск тестов

Проект содержит **23 автоматических теста**, покрывающих все сценарии ТЗ:
- Тесты API (`test_api.py`): авторизация, валидация, создание платежа, запись в outbox, идемпотентность, выборка по `payment_id`, ошибки 400/401/404/409/422.
- Тесты сервиса (`test_service.py`): Unit-тесты `PaymentsService`, проверка дублей, обновление статусов.
- Тесты Relay (`test_relay.py`): выборка pending-событий, публикация в брокер, обработка ошибок брокера, ретраи.
- Тесты Consumer (`test_consumer.py`): эмуляция шлюза, отправка вебхуков с повторными попытками (1с, 2с, 4с), DLQ при превышении 3 попыток, DLQ при отсутствии `payment_id`, идемпотентность при повторной доставке.

### Запуск тестов через `uv`:

```bash
uv run pytest
```

### Запуск с подробным выводом:

```bash
uv run pytest -v
```

Тесты выполняются изолированно в памяти (`sqlite+aiosqlite:///:memory:`) и не требуют запущенных внешних серверов PostgreSQL или RabbitMQ.

---

## 📡 Примеры использования API

Интерактивная документация Swagger UI доступна по адресу:
👉 **http://localhost:8888/docs**

Все эндпоинты защищены статическим ключом **`X-API-Key: test-secret-api-key-12345`**.

---

### 1. Создание платежа

**Запрос:**
```bash
curl -X POST "http://localhost:8888/api/v1/payments" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-secret-api-key-12345" \
  -H "Idempotency-Key: order-unique-key-1001" \
  -d '{
    "amount": 499.90,
    "currency": "RUB",
    "description": "Оплата подписки Премиум",
    "webhook_url": "https://httpbin.org/post",
    "metadata": {
      "user_id": 42,
      "tariff": "premium_monthly"
    }
  }'
```

**Ответ (`202 Accepted`):**
```json
{
  "payment_id": "14745603-9846-43d5-b10a-a7d396fe1295",
  "status": "pending",
  "created_at": "2026-10-16T05:07:50.400650Z"
}
```

---

### 2. Защита от дублей (Повтор с тем же Idempotency-Key)

При повторной отправке запроса с тем же значением заголовка `Idempotency-Key`:

**Ответ (`409 Conflict`):**
```json
{
  "message": "Платеж с ключом идемпотентности 'order-unique-key-1001' уже существует"
}
```

---

### 3. Получение информации о платеже

**Запрос:**
```bash
curl -X GET "http://localhost:8888/api/v1/payments/14745603-9846-43d5-b10a-a7d396fe1295/" \
  -H "X-API-Key: test-secret-api-key-12345"
```

**Ответ (`200 OK` после завершения обработки consumer'ом):**
```json
{
  "payment_id": "14745603-9846-43d5-b10a-a7d396fe1295",
  "amount": 499.90,
  "currency": "RUB",
  "description": "Оплата подписки Премиум",
  "metadata": {
    "user_id": 42,
    "tariff": "premium_monthly"
  },
  "status": "succeeded",
  "idempotency_key": "order-unique-key-1001",
  "webhook_url": "https://httpbin.org/post",
  "created_at": "2026-10-16T05:07:50.400650Z",
  "processed_at": "2026-10-16T05:07:53.438314Z"
}
```

---

### 4. Платеж не найден

**Запрос:**
```bash
curl -X GET "http://localhost:8888/api/v1/payments/00000000-0000-0000-0000-000000000000/" \
  -H "X-API-Key: test-secret-api-key-12345"
```

**Ответ (`404 Not Found`):**
```json
{
  "message": "Платеж с ID '00000000-0000-0000-0000-000000000000' не найден"
}
```

---

### 5. Ошибка авторизации (Отсутствует или неверный API-ключ)

**Запрос:**
```bash
curl -X GET "http://localhost:8888/api/v1/payments/14745603-9846-43d5-b10a-a7d396fe1295/"
```

**Ответ (`401 Unauthorized`):**
```json
{
  "message": "Неверный или отсутствующий API ключ"
}
```

---

### 6. Ошибка валидации (Сумма <= 0 или неверная валюта)

**Запрос:**
```bash
curl -X POST "http://localhost:8888/api/v1/payments" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-secret-api-key-12345" \
  -H "Idempotency-Key: order-unique-key-1002" \
  -d '{
    "amount": -10.0,
    "currency": "RUB",
    "description": "Тест",
    "webhook_url": "https://httpbin.org/post"
  }'
```

**Ответ (`422 Unprocessable Entity`):**
```json
{
  "message": "Ошибка валидации запроса",
  "details": [
    {
      "type": "greater_than",
      "loc": ["body", "amount"],
      "msg": "Input should be greater than 0",
      "input": -10.0
    }
  ]
}
```

---

### 7. Тестовый эндпоинт для приема вебхуков

Для локальной проверки отправки вебхуков реализован эндпоинт:
```bash
curl -X POST "http://localhost:8888/api/v1/payments/test-webhook/" \
  -H "Content-Type: application/json" \
  -d '{"status": "succeeded", "payment_id": "14745603-9846-43d5-b10a-a7d396fe1295"}'
```

**Ответ (`200 OK`):**
```json
{
  "status": "ok",
  "received": {
    "status": "succeeded",
    "payment_id": "14745603-9846-43d5-b10a-a7d396fe1295"
  }
}
```

---

## 🔍 Мониторинг и логирование

- **Логи Consumer**:
  ```bash
  docker compose logs -f consumer
  ```
- **Логи API / Outbox Relay**:
  ```bash
  docker compose logs -f api
  ```
- **Панель управления RabbitMQ Management**:
  Доступна в браузере: **http://localhost:15672**  
  (Логин: `guest`, Пароль: `guest`)  
  Очереди:
  - `payments.new` — очередь входящих платежей для обработки
  - `payments.retry` — очередь отложенных повторных попыток (TTL 5000 мс)
  - `payments.dlq` — Dead Letter Queue для окончательно неудавшихся сообщений
