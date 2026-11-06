# audiodoc

Бэкенд для Telegram-бота: распознавание аудио через Whisper и извлечение текста из документов.

Отдельный FastAPI-сервис для Telegram-бота. Он предоставляет `/transcribe` для распознавания аудио Whisper и `/process-document` для извлечения текста Document Engine. Бот остаётся HTTP-клиентом; изображения, анимации и видео обрабатываются на стороне бота.

## Возможности

- Распознавание речи с помощью `faster-whisper`.
- Извлечение текста из PDF (включая OCR сканов), DOCX, XLSX, PPTX, ODT, ODS, ODP, EPUB, FB2, DJVU (включая OCR), TXT, Markdown, HTML, XML, CSV и RTF.
- Отдельные Bearer-ключи для Whisper и Document Engine.
- Ограничения размера файлов, длительности аудио, времени обработки, текста, таблиц, OCR, внешних программ и очередей.
- Диагностика зависимостей через `/ready`, корреляция логов через `X-Request-ID`, фильтрация секретов.

Старые форматы Office (`.doc`, `.xls`, `.ppt`) и отдельные изображения не поддерживаются. Обработку изображений, анимаций и видео выполняет бот.

## Требования

Требуется Python 3.11 или новее.

Пример для Debian/Ubuntu (названия пакетов зависят от выпуска ОС):

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng djvulibre-bin
```

Для OCR нужны `tesseract` и языки `rus`, `eng`. Для DJVU нужны `djvutxt`, `djvused` и `ddjvu`. Их наличие можно проверить через `GET /ready`.

## Быстрый запуск

Из корневого каталога проекта:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-lock.txt
cp .env.example .env
chmod 600 .env
```

Отредактируйте `.env`: задайте **два разных длинных случайных ключа** `WHISPER_API_KEY` и `DOCUMENT_API_KEY`. Такие же соответствующие значения должны быть в `.env` бота. Не включайте `ALLOW_UNAUTHENTICATED` на рабочем сервере.

Сгенерировать ключ можно командой:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Запуск для локальной проверки:

```bash
uvicorn app:app --host 127.0.0.1 --port 8000
```

Для двух машин привяжите сервис к адресу приватной сети/VPN, а не к `0.0.0.0`. Примеры UFW, WireGuard, nginx и systemd находятся в `deploy/`. Перед применением замените все адреса и пути на свои и сначала разрешите SSH администратора в файрволе.

При первом запуске `faster-whisper` может скачать модель. Для изолированной машины заранее подготовьте локальную модель, задайте `WHISPER_MODEL_PATH` и `WHISPER_OFFLINE=true`; см. `docs/operations.md`.

## Проверка

```bash
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/ready \
  -H "Authorization: Bearer $DOCUMENT_API_KEY"
```

`/health` — liveness без ключа. `/ready` — диагностика системных зависимостей, защищённая ключом документов. По умолчанию `/docs` и `/openapi.json` выключены.

Проверка документа:

```bash
curl -i \
  -H "Authorization: Bearer $DOCUMENT_API_KEY" \
  -F "file=@sample.txt" \
  http://127.0.0.1:8000/process-document
```

Не передавайте ключ в командной строке в рабочем окружении: пример с переменной показан для локальной проверки. Для бота адреса должны включать полные пути `/transcribe` и `/process-document`.

## Настройки окружения

Все настройки и безопасные значения по умолчанию перечислены в `.env.example`.

| Переменная | По умолчанию | Назначение |
|---|---:|---|
| `WHISPER_API_KEY` | пусто | Отдельный Bearer-ключ `/transcribe`; пустое значение допустимо только при локальном bypass |
| `DOCUMENT_API_KEY` | пусто | Отдельный Bearer-ключ `/process-document` и `/ready` |
| `ALLOW_UNAUTHENTICATED` | `false` | Локальный обход авторизации; не включать на сервере |
| `BACKEND_TEMP_DIR` | `tmp/` в корне проекта | Приватный каталог временных файлов |
| `MAX_AUDIO_SIZE` | `26214400` | Максимум байтов аудиофайла (25 МиБ) |
| `MAX_AUDIO_DURATION` | `600` | Максимальная длительность аудио в секундах |
| `MAX_CONCURRENT_TRANSCRIPTIONS` | `1` | Число активных распознаваний |
| `MAX_WAITING_DOCUMENTS` | `4` | Число ожидающих задач документов (активных — 2) |
| `MAX_WAITING_TRANSCRIPTIONS` | `4` | Число ожидающих задач Whisper |
| `WHISPER_MODEL_SIZE` | `small` | Имя модели, если локальный путь не задан |
| `WHISPER_MODEL_PATH` | пусто | Путь к заранее загруженной локальной модели; приоритетнее имени |
| `WHISPER_DEVICE` | `cpu` | Устройство модели (`cpu` или поддерживаемое `cuda`) |
| `WHISPER_COMPUTE_TYPE` | `int8` | Тип вычислений, совместимый с выбранным устройством |
| `WHISPER_OFFLINE` | `false` | Передаёт `local_files_only=true`, запрещая скачивание модели |
| `WHISPER_CPU_THREADS` | `6` | Число CPU-потоков Whisper |
| `WHISPER_LANGUAGE` | `ru` | Подсказка языка распознавания |
| `WHISPER_BEAM_SIZE` | `5` | Beam size Whisper |
| `ENABLE_DOCS` | `false` | Включает `/docs` и `/openapi.json`; только для доверенной среды разработки |
| `LOG_LEVEL` | `INFO` | Уровень журналирования Python |

Дополнительные фиксированные лимиты Document Engine расположены в `backend/document_engine/limits.py`: документ 50 МиБ, 500 страниц, до 2 000 000 символов, 180 секунд общей обработки, до 2 активных документов, ограничения ZIP, таблиц, изображений OCR и DJVU.

## Тесты

Установите зависимости разработки и запустите наборы отдельно:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m pytest -q -m integration
```

Интеграционные тесты требуют Tesseract с языками `rus` и `eng`, а также DjVuLibre. Для Whisper используется подставная модель: настоящая модель не скачивается и не загружается. Перед тестами установите Python-зависимости из `requirements-lock.txt`. См. `docs/operations.md`.

## Документация

- [Архитектура (EN)](docs/architecture.md) · [Архитектура (RU)](docs/architecture.ru.md)
- [HTTP API](docs/api.md)
- [Эксплуатация](docs/operations.md)
- [Добавление формата](docs/adding-a-format.md)
- [Чек-лист безопасности](docs/security-checklist.md)
- [Чек-лист приёмки развёртывания (исторический)](docs/history/final-acceptance.md)
- [Примеры развёртывания](deploy/README.md)
- [История рефакторинга](docs/history/REFACTORING_LOG.md)
