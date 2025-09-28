# ClipSafe DL

Телеграм-бот для без потерь операций с видео: ремукс, lossless-обрезка (включая точный «smart»-режим), извлечение аудио и генерация превью. Репозиторий содержит каркас сервиса «ClipSafe DL» с очередью задач, FFmpeg-воркером, подтверждением прав на контент и интеграцией Prometheus/Alembic.

## Особенности
- По умолчанию копируем исходные потоки (`-c copy`); перекодирование выполняется только по запросу (smart-trim).
- Поддержаны загрузки через Telegram и прямые HTTP(S) ссылки с валидацией заголовков, доменов и диапазонов.
- Расширенное хранилище: локально/Nginx через `CLIPSAFE_PUBLIC_BASE_URL` или S3/MinIO (настройки `CLIPSAFE_S3_*`) с автоматической выгрузкой и TTL-очисткой.
- Промежуточные и результативные файлы автоматически очищаются по `CLIPSAFE_RESULT_TTL_H`.
- Подтверждение прав на контент реализовано через FSM-диалог: пока пользователь не подтвердит права, задача остаётся черновиком.
- Антиспам ограничивает число задач в час на пользователя.
- Prometheus-метрики для мониторинга и Alembic для миграций БД.

## Пользовательские сценарии
- **Файл в чат.** После загрузки бот просит подтвердить права, затем предлагает операции: «Оставить оригинал», «Ремукс», «Вырезать», «Аудио», «Превью».
- **Прямая ссылка.** Выполняется HEAD-запрос, проверяются лимиты и домен, далее сценарий идентичен файлу.
- **YouTube/TikTok.** Возвращается отказ с предложением загрузить исходник; скачивание контента не выполняется.

## Команды бота
- `/start` — приветствие и обзор возможностей.
- `/help` — справка по операциям и ограничениям.
- `/upload` — подсказка по форматам и лимитам.
- `/link` — инструкция по работе с прямыми ссылками.
- `/trim` — пояснение по форматам временных меток.
- `/format` — выбор контейнера (MP4/MKV) с предупреждением о совместимости.
- `/queue` — последние задачи пользователя.
- `/cancel` — отмена последнего черновика.

## Архитектура (Python стек)
```
app/
  __init__.py
  __main__.py        # точка входа бота
  analytics.py       # условная аналитика (логирование событий)
  antispam.py        # ограничения по числу задач
  auth.py            # отказ по платформам, хелперы прав
  bot.py             # обработчики aiogram + FSM подтверждения
  commands.py        # регистрация /setmycommands
  config.py          # загрузка CLIPSAFE_* переменных
  ffmpeg_ops.py      # фабрики команд FFmpeg
  jobs.py            # Redis-очередь, черновики, статусы
  logs.py            # конфигурация логов
  metrics/           # Prometheus счётчики/гейджи
  migrations.py      # запуск Alembic (upgrade head)
  orm.py             # SQLAlchemy модели
  prometheus_exporter.py
  services/
    downloader.py    # Telegram/HTTP-загрузчик
    ffmpeg_runner.py # операции FFmpeg (включая smart trim)
    storage_backend.py # локальное/S3 хранилище + TTL cleanup
  states.py          # FSM состояния aiogram
  storage.py         # утилиты путей
  texts.py           # текстовые шаблоны
  worker.py          # асинхронный FFmpeg-воркер
alembic/
  env.py, versions/  # миграции (см. alembic.ini)
alembic.ini
Dockerfile
compose.yaml
pyproject.toml
.env.example
```

## Хранилище и выдача результатов
- Файлы сохраняются в `CLIPSAFE_STORAGE_ROOT/<job_id>/`. При заданном `CLIPSAFE_PUBLIC_BASE_URL` формируется ссылка вида `<base>/<job_id>/<filename>` — удобно для Nginx.
- Для S3/MinIO укажите `CLIPSAFE_S3_ENDPOINT`, `CLIPSAFE_S3_BUCKET`, `CLIPSAFE_S3_REGION`, ключи и (опционально) `CLIPSAFE_S3_PUBLIC_BASE` — результаты будут выгружены в бакет и приведена публичная ссылка.
- `StorageBackend.cleanup_expired()` автоматически удаляет устаревшие результаты (локально и в S3) на основе TTL (`CLIPSAFE_RESULT_TTL_H`). Воркер вызывает очистку каждые 30 минут.

## Подтверждение прав
- После загрузки файла/ссылки бот запускает FSM-диалог: пользователь должен подтвердить права.
- Пока права не подтверждены, операции недоступны, а задача остаётся в черновиках.
- Отказ — задача удаляется, можно загрузить позднее.

## Smart trim
- Быстрая обрезка (`smart=False`) выполняется без перекодирования (`-c copy`).
- Точный режим (`smart=True`) перекодирует только выбранный отрезок (`libx264` + `-c:a copy`) для корректного старта/финиша.
- Выбор режима сохраняется в параметрах задачи; воркер автоматически подбирает нужную команду.

## Alembic и БД
- Базовые модели описаны в `app/orm.py`; первоначальная миграция `alembic/versions/0001_initial.py` создаёт таблицы `users`, `jobs`, `files`.
- `python -m app.migrations` — применить миграции (`upgrade head`). URL берётся из `CLIPSAFE_DATABASE_URL` или `alembic.ini`.

## Настройки окружения (.env)
```ini
CLIPSAFE_BOT_TOKEN=000000:your-telegram-bot-token
CLIPSAFE_REDIS_URL=redis://redis:6379/0
CLIPSAFE_MAX_FILE_GB=2
CLIPSAFE_MAX_DURATION_H=6
CLIPSAFE_RESULT_TTL_H=24
CLIPSAFE_JOBS_PER_HOUR=5
CLIPSAFE_ALLOWED_DOMAINS=example.com,cdn.example.org
CLIPSAFE_STORAGE_ROOT=/app/data
CLIPSAFE_PUBLIC_BASE_URL=
CLIPSAFE_WEBHOOK_URL=
CLIPSAFE_S3_ENDPOINT=
CLIPSAFE_S3_BUCKET=
CLIPSAFE_S3_REGION=
CLIPSAFE_S3_ACCESS_KEY=
CLIPSAFE_S3_SECRET_KEY=
CLIPSAFE_S3_PUBLIC_BASE=
CLIPSAFE_DATABASE_URL=
CLIPSAFE_PROMETHEUS_PORT=8001
```

## Быстрый запуск
1. Создайте окружение и установите зависимости:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -e .[dev]
   ```
2. Заполните `.env`.
3. Запустите Redis (`docker run --rm -p 6379:6379 redis:7`).
4. Примените миграции (опционально, если используется БД): `python -m app.migrations`.
5. Запустите бота: `python -m app`.
6. Запустите воркер: `python -m app.worker`.

Docker-вариант: `docker compose up --build` (включает bot, worker, redis).

## Мониторинг и логи
- Prometheus-экспортер стартует на `CLIPSAFE_PROMETHEUS_PORT` (по умолчанию 8001).
- Логи форматируются через `app/logs.py` (структурированный вывод в stdout).

## Тесты
```bash
pytest
```
Покрытие включает парсер таймкодов, антиспам и очистку хранилища.

## Возможные доработки
1. Настроить выдачу результатов через CDN или pre-signed S3 ссылки.
2. Добавить UI для выбора точек smart-trim и уведомление о предполагаемом перекодировании.
3. Расширить FSM (например, запрос типа лицензии) и добавить журнал подтверждений в БД.
4. Подключить реальные аналитические и уведомительные сервисы.
5. Расширить набор интеграционных тестов с реальными медиа.
