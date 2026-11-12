# audiodoc

Бэкенд для Telegram-бота: распознавание аудио через Whisper и извлечение текста из документов.

Отдельный FastAPI-сервис. Он предоставляет `/transcribe` для аудио и `/process-document` для извлечения текста из документов. Бот остаётся HTTP-клиентом; изображения, анимации и видео обрабатываются на стороне бота.

## Возможности

- Распознавание речи с помощью `faster-whisper`.
- Извлечение текста из PDF (включая OCR), DOCX, XLSX, PPTX, ODT, ODS, ODP, EPUB, FB2, DJVU (включая OCR), TXT, Markdown, HTML, XML, CSV и RTF.
- Отдельные Bearer-ключи для Whisper и Document Engine.
- Ограничения размера загрузок, времени обработки, извлечённого текста и очередей задач.
- Диагностика зависимостей через `/ready`, корреляция логов через `X-Request-ID`, фильтрация секретов.

Старые форматы Office (`.doc`, `.xls`, `.ppt`) и отдельные изображения не поддерживаются. Обработку изображений, анимаций и видео выполняет бот.

## Требования

Требуется Python 3.11 или новее. Для Debian/Ubuntu установите системные инструменты OCR и DJVU:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng djvulibre-bin
```

## Установка

### 1. Установщик релиза

Установщик проверяет контрольные суммы релиза и по умолчанию устанавливает audiodoc в `~/audiodoc/.venv`. Требуются Linux с glibc, Python 3.11+, `venv`, `curl` и `sha256sum` (Alpine не поддерживается). Перед запуском скачайте установщик и проверьте его содержимое:

```bash
curl -fsSLo install.sh https://raw.githubusercontent.com/WhlteAdmln/audiodoc/main/install.sh
less install.sh
sh install.sh --no-model --systemd
```

Параметры `--model`, `--device`, `--compute-type`, `--host` и `--port` настраивают установку; `--no-model` пропускает скачивание модели. `--systemd` создаёт пользовательский юнит, но не включает и не запускает его. Для другого каталога задайте `AUDIODOC_HOME`. Инструкции по обновлению приведены в [руководстве по эксплуатации](docs/operations.md).

### 2. Установка wheel релиза

Скачайте wheel и `constraints.txt` из одного GitHub Release. Установите пакет через pipx или pip:

```bash
pipx install --pip-args="--constraint constraints.txt" ./audiodoc-*.whl
# или
python -m pip install --constraint constraints.txt ./audiodoc-*.whl
audiodoc init
audiodoc doctor
```

### 3. Установка из исходников

```bash
git clone https://github.com/WhlteAdmln/audiodoc.git
cd audiodoc
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-lock.txt
cp .env.example .env
chmod 600 .env
```

## Настройка

Задайте разные длинные случайные значения для `AUDIODOC_AUDIO_KEY` и `AUDIODOC_DOCUMENT_KEY`; вне локальной разработки оставляйте `ALLOW_UNAUTHENTICATED=false`. Ключ можно создать командой `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Все настройки, значения по умолчанию, примеры и команду `audiodoc pair` см. в [руководстве по конфигурации](docs/configuration.md). Настройки бота описаны в [руководстве подключения](docs/connecting-the-bot.ru.md).

## Запуск и проверка

Для локального запуска из исходников:

```bash
uvicorn app:app --host 127.0.0.1 --port 8000
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/ready \
  -H "Authorization: Bearer $AUDIODOC_DOCUMENT_KEY"
```

`/health` не требует ключа. Для `/ready` нужен `AUDIODOC_DOCUMENT_KEY`. Привязывайте сервис к приватному/VPN-адресу или loopback за TLS reverse proxy; не открывайте его в недоверенной сети. Для автономного запуска заранее подготовьте локальную модель и задайте `WHISPER_MODEL_PATH` и `WHISPER_OFFLINE=true`; см. [руководство по эксплуатации](docs/operations.md).

## Тесты

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m pytest -q -m integration
```

Интеграционные тесты требуют Tesseract с языками `rus` и `eng`, а также DjVuLibre. Для Whisper используется подставная модель: настоящая модель не загружается.

## Документация

- [Архитектура (EN)](docs/architecture.md) · [Архитектура (RU)](docs/architecture.ru.md)
- [HTTP API](docs/api.md) · [Настройка](docs/configuration.md)
- [Подключение Telegram-бота](docs/connecting-the-bot.ru.md)
- [Эксплуатация и production-развёртывание](docs/operations.md)
- [Добавление формата](docs/adding-a-format.md) · [Чек-лист безопасности](docs/security-checklist.md)
