# Асинхронный микросервис процессинга платежей

Микросервис для асинхронной обработки платежей с защитой от дублей (идемпотентность), гарантированной доставкой событий (Outbox Pattern), очередями сообщений через RabbitMQ, эмуляцией платежного шлюза, отправкой Webhook уведомлений с повторными попытками (retries) и очередью недоставленных сообщений (Dead Letter Queue).

---

## 🛠 Стек технологий

- **Язык**: Python 3.12+ / 3.13
- **Web-фреймворк**: FastAPI + Pydantic v2
- **База данных**: PostgreSQL 16
- **ORM**: SQLAlchemy 2.0 (асинхронный режим, asyncpg)
- **Миграции**: Alembic
- **Брокер сообщений**: RabbitMQ (FastStream)
- **HTTP-клиент**: HTTPX (с экспоненциальными ретраями)
- **Контейнеризация**: Docker + Docker Compose

---

## 🏛 Архитектура решения

1. **Создание платежа (API)**:
   - Клиент отправляет `POST /api/v1/payments` с обязательными заголовками `X-API-Key` и `Idempotency-Key`.
   - Если платеж с таким `Idempotency-Key` уже существует, возвращается `409 Conflict`.
   - В рамках **единой транзакции БД** создается запись в таблице `payments` со статусом `pending` и формируется событие `PaymentCreated` в таблице `outbox` со статусом `pending` (**Outbox Pattern**).
   - Клиенту возвращается статус `202 Accepted` с `payment_id`, `status` и `created_at`.

2. **Outbox Relay (Издатель)**:
   - Фоновый процесс выбирает события из таблицы `outbox` (`status = pending`) с блокировкой строк (`skip_locked=True`).
   - Сообщения публикуются в очередь RabbitMQ `payments.new` как `persistent`.
   - Статус записи в `outbox` обновляется на `success`.

3. **Consumer (Обработчик платежей)**:
   - Слушает очередь `payments.new`.
   - **Идемпотентность**: проверяет текущий статус платежа в БД; если платеж уже завершен (`succeeded` или `failed`), повторная обработка пропускается.
   - **Эмуляция шлюза**: эмулирует задержку обработки (2–5 секунд) и вероятность успеха (90% успех, 10% ошибка).
   - **Обновление БД**: фиксирует итоговый статус (`succeeded` / `failed`) и время завершения `processed_at`.
   - **Webhook уведомление**: отправляет POST-запрос с результатами платежа на указанный `webhook_url`.
   - **Retry & DLQ**:
     - При сбоях отправки вебхука выполняется до 3 повторных попыток с экспоненциальной задержкой (1с, 2с, 4с).
     - При критической системной ошибке сообщение отклоняется (`reject(requeue=False)`) и попадает в `payments.retry` (с TTL 5000 мс), откуда автоматически возвращается в `payments.new`.
     - При превышении лимита повторных попыток (по заголовку `x-death`) сообщение отправляется в Dead Letter Queue (`payments.dlq`).

---

## 📂 Структура проекта

```
PaymentsProccessor/
├── .env.docker.example      # Переменные окружения для API и Consumer в Docker
├── .env.postgres.example    # Переменные окружения для PostgreSQL
├── .env.rabbit.example      # Переменные окружения для RabbitMQ
├── docker-compose.yml       # Конфигурация 4 сервисов (postgres, rabbitmq, backend, consumer)
├── Dockerfile               # Multi-stage сборка приложения через uv
├── pyproject.toml           # Зависимости проекта
├── alembic.ini              # Конфигурация Alembic
├── src/
│   ├── api/                 # FastAPI роуты, зависимости, схемы ошибок и примеров
│   ├── broker/              # RabbitMQ менеджер, consumer, publisher, relay
│   ├── config.py            # Централизованные Pydantic настройки проекта
│   ├── db/                  # Подключение и DBManager (Unit of Work)
│   ├── migrations/          # Миграции Alembic (таблицы payments и outbox)
│   ├── models/              # SQLAlchemy ORM модели (PaymentORM, OutboxORM)
│   ├── repos/               # Репозитории (PaymentsRepo, OutboxRepo)
│   ├── schemas/             # Pydantic DTO (запросы, ответы, события)
│   ├── services/            # Бизнес-логика (PaymentsService)
│   └── utils/               # Enums и кастомные исключения
```

---

## 🚀 Запуск через Docker Compose

Все сервисы настраиваются через публичные `.example` файлы, которые не содержат критических секретов и коммитятся в репозиторий.

### Запуск всех контейнеров:

```bash
docker compose up -d --build
```

Compose поднимает 4 сервиса:
1. `payments_postgres` — PostgreSQL 16 (порт `6432:5432`)
2. `payments_rabbitmq` — RabbitMQ 3.11 Management (порты `5672` и `15672`)
3. `payments_backend` — FastAPI API сервис (порт `8888:8888`, выполняет миграции и Outbox Relay)
4. `payments_consumer` — Consumer фоновой обработки платежей

### Проверка статуса сервисов:

```bash
docker compose ps
```

---

## 📡 Примеры использования API

Интерактивная документация Swagger UI доступна по адресу:
👉 **http://localhost:8888/docs**

### 1. Создание платежа

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

### 2. Защита от дублей (Повтор с тем же Idempotency-Key)

При повторной отправке запроса с тем же заголовком `Idempotency-Key`:

**Ответ (`409 Conflict`):**
```json
{
  "message": "Платеж с ключом идемпотентности 'order-unique-key-1001' уже существует"
}
```

### 3. Получение информации о платеже

```bash
curl -X GET "http://localhost:8888/api/v1/payments/14745603-9846-43d5-b10a-a7d396fe1295" \
  -H "X-API-Key: test-secret-api-key-12345"
```

**Ответ (`200 OK` после обработки consumer'ом):**
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

## 🔍 Мониторинг и логирование

- **Логи Consumer**:
  ```bash
  docker logs -f payments_consumer
  ```
- **Логи Backend / Outbox Relay**:
  ```bash
  docker logs -f payments_backend
  ```
- **Панель управления RabbitMQ**:
  Доступна по адресу: **http://localhost:15672**
  (Логин: `guest`, Пароль: `guest`)
  Очереди:
  - `payments.new` — очередь входящих платежей
  - `payments.retry` — очередь отложенных повторных попыток (TTL)
  - `payments.dlq` — Dead Letter Queue для окончательно неудавшихся сообщений
