> Исторический документ. На момент описанных работ проект назывался `whisper-server`, затем `Media Backend`; актуальное имя проекта — `audiodoc`. Содержание ниже сохранено как запись истории и не является текущей инструкцией по развёртыванию.

# Журнал рефакторинга

| № | Название | Статус | Кратко | Открытые вопросы |
|---|---|---|---|---|
| 0 | Приёмка и страховка | принято | Созданы `tests/`, pytest-конфигурация, контрактные и integration-тесты; исправление `00-r2` принято пользователем (30 passed, 4 integration passed) | нет |
| 1 | Срочная защита (в старой структуре) | принято | Bearer-аутентификация, лимиты HTTP и аудиозагрузки, потоковый Whisper с пределом параллельности и длительности, приватные временные файлы, ограниченное чтение ZIP `mimetype`; пользователь подтвердил 49 passed и 5 integration passed | Настройка ключей и сетевых мер D.1/D.2 остаётся эксплуатационной задачей пользователя |
| 2 | Каркас проекта | принято | Создан пакет `backend/`; перенесены Document Engine, API, загрузки и Whisper; добавлены `config/`, `errors/`, `common/`; пользователь подтвердил 54 passed и 5 integration passed, Whisper small загружена, `/health` отвечает 200 | нет |
| 3 | Ядро Document Engine (A2 + A3) | принято | Созданы пакеты `detection/`, `guards/`, `ocr/`, `result.py`; удалены старые монолитные `detector.py`, `archive_guard.py`, `ocr.py`; пользователь подтвердил 65 passed и 5 integration passed, импорты и запуск Uvicorn успешны | нет |
| 4 | Текстовые форматы, часть 1 (A4) | принято | TXT/MD, HTML, XML, CSV и RTF вынесены в `extractors/`; пользователь подтвердил 72 passed и 5 integration passed, запуск Uvicorn успешен | нет |
| 5 | Форматы Office, часть 2 (A4) | принято | DOCX, XLSX и PPTX вынесены в отдельные экстракторы; пользователь подтвердил 75 passed и 5 integration passed, запуск Uvicorn и штатное завершение | нет |
| 6 | ODF: ODT, ODS и ODP (A4) | принято | Общая загрузка вынесена в `extractors/odf/__init__.py`; извлечение разделено на `odt.py`, `ods.py`, `odp.py`; пользователь подтвердил 79 passed и 5 integration passed, Uvicorn штатно завершён | нет |
| 7 | EPUB и FB2 (A4) | принято | EPUB и FB2 вынесены в `extractors/epub.py` и `extractors/fb2.py`; пользователь подтвердил 84 passed и 5 integration passed, Uvicorn запустился и завершился штатно | нет |
| 8 | PDF и DJVU (A4) | принято | PDF вынесен в `extractors/pdf.py`; DJVU разделён на `tools.py`, `text_layer.py`, `ocr_pages.py` и `__init__.py`; пользователь подтвердил 95 passed и 5 integration passed | На машине пользователя проверить DJVU с установленным DjVuLibre |
| 9 | Pipeline, Runner и Registry (A5) | принято | Созданы `extractors/REGISTRY`, `pipeline.py`, `runner.py`; `processor.py` оставлен совместимым shim; пользователь подтвердил 102 passed, 5 integration passed, запуск Uvicorn и оба варианта импорта | нет |
| 10 | Whisper и HTTP-слой (A6 + A7) | принято | ModelHolder, отдельные API-роутеры и Lifespan; исправление r2 проверено пользователем: 109 passed, 5 integration passed, Whisper small загружена, `/health` отвечает 200 | нет |
| 11 | Финальная чистка (A8) | принято | Удалён `processor.py` shim; добавлены тесты границ пакетов, архитектурные документы RU/EN и docstrings; пользователь подтвердил 115 passed, 5 integration passed, Uvicorn и отсутствие shim | нет |
| 12 | Очереди и сроки (B.4 + B.13) | принято | Общий deadline документов, ограниченный runner подпроцессов, конечные очереди документов/Whisper, HTTP 503 с `Retry-After`; пользователь подтвердил 128 passed, 5 integration passed и успешный запуск Whisper small | Нагрузочную проверку 10 параллельных запросов можно выполнить дополнительно |
| 13 | Лимиты документов (B.5 + B.7 + B.8 + B.9) | принято | Pixel-safe PDF DPI; общий TextBudget и ExtractContext, пределы XLSX/ODS, max_characters и truncated; предварительная проверка OCR, кеш Tesseract; ограниченные DJVU subprocess/рендер/страницы | На машине пользователя проверить большой PDF/XLSX и реальный DJVU с DjVuLibre |
| 14 | XML, ошибки, зависимости (B.10 + B.11 + B.12) | принято | Защищённый XML, безопасные HTTP-ошибки и логи, конфигурация OpenAPI/Whisper, очищенные и закреплённые зависимости; пользователь подтвердил 154 passed, 5 integration passed, загрузку Whisper small и 404 для `/docs`/`/openapi.json` | Офлайн-запуск Whisper остаётся эксплуатационной проверкой D.8.13 |
| 15 | Документация, развёртывание и журналы (часть C + выбранные D) | принято | README RU/EN, API/operations/architecture/security docs, deploy templates, `/ready`, X-Request-ID и SecretsFilter; пользователь подтвердил 161 passed, 5 integration passed, `/ready` 200 с native tools и Whisper загруженной | Применить и проверить инфраструктурные шаблоны на тестовой машине |
| 16 | Финальная приёмка | готово, ожидает проверки | Сверка B.0 и D.8, обновлённый аудит, исправлен недостижимый обработчик BackendError и удалены неиспользуемые записи из lock-файла | Остались эксплуатационные пункты D.8; см. `docs/final-acceptance.md` |


## Принятые решения
- HTTP-контракт с ботом сохраняется: `POST /transcribe`, `POST /process-document`, multipart-поле `file` и прежние поля JSON-ответов.
- Самостоятельные изображения (PNG/JPEG/GIF и другие) не относятся к Document Engine: детектор возвращает `None`, обработчик документа отклоняет их.
- Интеграционные проверки OCR, PDF OCR, DJVU и HTTP-распознавания вынесены под маркер `integration`.
- Тестовые документы создаются фабриками в `tests/builders.py`; сами тесты используют временные каталоги pytest.
- Архив бота остаётся только образцом и в поставку не включается.
- Доступ к `/transcribe` и `/process-document` защищён разными Bearer-ключами. По умолчанию отсутствие любого ключа останавливает запуск; `ALLOW_UNAUTHENTICATED=true` предназначен только для локальной разработки и тестов.
- Для ротации ключей поддерживается список через запятую: новый и старый ключи могут временно действовать одновременно.
- Тело HTTP-запроса ограничено `max(MAX_DOCUMENT_SIZE, MAX_AUDIO_SIZE) + 1 МиБ`; отдельные аудио и документы дополнительно ограничиваются при чтении/сохранении.
- Параметры аудио по умолчанию: `MAX_AUDIO_SIZE=25 МиБ`, `MAX_AUDIO_DURATION=600` секунд, `MAX_CONCURRENT_TRANSCRIPTIONS=1`.
- Приём новых задач ограничен очередями: документы — 2 активных + 4 ожидающих; транскрибация — 1 активная + 4 ожидающих (ожидание настраивается через `MAX_WAITING_DOCUMENTS` и `MAX_WAITING_TRANSCRIPTIONS`). Переполнение возвращает HTTP 503 и `Retry-After: 30`.
- Обработка одного документа имеет общий срок 180 секунд; отдельные циклы экстракторов и OCR проверяют остаток времени.
- Whisper выполняется через `asyncio.to_thread`; лимит параллельности защищает CPU машины, общей с LLM.
- Временные аудиофайлы размещаются в `TEMP_DIR` (по умолчанию `whisper-server/tmp` или путь `BACKEND_TEMP_DIR`), каталог имеет права `0700`, файл — `0600`; забытые файлы старше часа удаляются при старте. Очистка затрагивает только файлы с UUID-именами, созданные этим модулем.
- ZIP-детектор читает не более 200 байт из члена `mimetype`; порядок и остальные проверки определения формата сохранены.
- Конфигурация теперь централизована в `backend.config.settings.settings`; `.env` загружается из корня проекта до импорта настроек.
- Импорты рабочих модулей и тестов используют единый префикс `backend.*`; точка запуска `uvicorn app:app` и импорт `from app import app` сохранены.

## Известные отклонения от плана
- Модули аутентификации и HTTP-лимитов из поставки 1 перенесены сразу в `backend/api/`, ограниченные операции с загрузками — в `backend/common/`, а Whisper и временные файлы — в `backend/transcription/`. Это сохраняет изменения безопасности до последующего структурного разбиения API и Document Engine.
- `backend/common/` содержит `text_budget.py`, `deadline.py`, `subprocess_runner.py`, `logging_setup.py`, `work_queue.py`, `request_id.py`, `log_filters.py` и другие небольшие общие инструменты; фильтры логов и X-Request-ID реализованы в поставке 15.
- В `backend/errors/` добавлены классы из A1, а также `AudioTooLongError` и `ModelNotReadyError`, ранее находившиеся в сервисе Whisper.
- `app.py` является тонкой точкой входа; приложение и lifecycle находятся в `backend/main.py` и используют FastAPI lifespan.
- В среде ассистента отсутствуют `faster-whisper`, `EbookLib` и `striprtf`: связанные тесты пропускаются. Настоящая модель Whisper не запускалась.
- Сетевые меры D.1/D.2 (приватный адрес, VPN/TLS, файрвол, фактическая установка и ротация секретов) не выполняются из архива; это действия пользователя на машинах A и B.

## Проверки поставки 1 (принята пользователем)
- `python -m pytest -q` → пользователь сообщил: 49 passed, 5 deselected.
- `python -m pytest -q -m integration` → пользователь сообщил: 5 passed, 49 deselected.
- Ручной запрос `POST /process-document` с действующим Bearer-ключом → HTTP 200 и прежняя структура ответа.

## Проверки поставки 2
- `python -m pytest -q` → 35 passed, 7 skipped, 1 deselected.
- `python -m pytest -q -m integration` → 1 passed, 6 skipped, 36 deselected.
- `python -m compileall -q app.py backend tests` → успешно.
- Проверка наличия целевой структуры, отсутствия прежних корневых модулей и старых импортов → успешно.


## Проверки поставки 2 (принята пользователем)
- `python -m pytest -q` → пользователь сообщил: 54 passed, 5 deselected.
- `python -m pytest -q -m integration` → пользователь сообщил: 5 passed, 54 deselected.
- Запуск Uvicorn → Whisper small загружена; `/health` → `{"status":"ok","model":"small","loaded":true}`.
- Импорт `backend.document_engine.detector` → OK на проверочной машине пользователя (позднее модуль перенесён в `backend.document_engine.detection`).

## Проверки поставки 3
- `python -m pytest -q` → 46 passed, 7 skipped, 1 deselected.
- `python -m pytest -q -m integration` → 1 passed, 6 skipped, 47 deselected.
- `python -m compileall -q app.py backend tests` → успешно.
- Проверка импортов новых пакетов `detection`, `guards`, `ocr`, `result` → успешно.
- Проверка старых импортов `backend.document_engine.detector`, `backend.document_engine.archive_guard` и старого модуля `backend.document_engine.ocr.py` → остаточных ссылок нет; старые файлы удалены.
- Проверка централизованных констант `MAX_IMAGE_PIXELS` и `OCR_PAGE_TIMEOUT` → определения остались только в `limits.py`.
- Реальный запуск приложения/Whisper в среде ассистента не выполнялся: здесь отсутствуют `faster-whisper`, `EbookLib` и `striprtf`; пользователь сможет повторить проверку после распаковки архива.


## Проверки поставки 3 (принята пользователем)
- `python -m pytest -q` → пользователь сообщил: 65 passed, 5 deselected.
- `python -m pytest -q -m integration` → пользователь сообщил: 5 passed, 65 deselected.
- Импорты `detection`, `ocr`, `guards` → OK на машине пользователя.
- Запуск Uvicorn → успешно.

## Проверки поставки 4
- `python -m pytest -q` → 52 passed, 8 skipped, 1 deselected.
- `python -m pytest -q -m integration` → 1 passed, 6 skipped, 54 deselected.
- `python -m compileall -q app.py backend tests` → успешно.
- Изолированные проверки TXT/MD, HTML, XML и CSV → успешно; RTF-тест пропущен, так как в среде ассистента отсутствует `striprtf`.
- Smoke-проверка маршрутизации `process_document_sync` для TXT, MD, HTML, XML и CSV → успешно. Для импорта монолитного `processor.py` отсутствующие optional-пакеты `ebooklib` и `striprtf` временно подменялись тестовыми модулями в одноразовом процессе; эти заглушки в проект/архив не добавлялись.
- `processor.py` больше не содержит реализаций пяти вынесенных экстракторов; новые функции имеют сигнатуру `(data: bytes) -> str`.
- Изменения поведения не планировались; преобразование результатов продолжает использовать `build_result`.
- Полный end-to-end прогон RTF через установленную библиотеку `striprtf` не выполнен в среде ассистента.


## Проверки поставки 5
- `python -m pytest -q` → 55 passed, 8 skipped, 1 deselected.
- `python -m pytest -q -m integration` → 1 passed, 6 skipped, 57 deselected.
- `python -m compileall -q app.py backend tests` → успешно.
- Изолированные unit-тесты новых DOCX/XLSX/PPTX-экстракторов → успешно.
- Сравнение результатов новых экстракторов с функциями из предыдущего `processor.py` на одних и тех же сгенерированных документах → точное совпадение текстового результата для DOCX (45 символов), XLSX (62 символа), PPTX (48 символов).
- Старые `_extract_docx`, `_extract_xlsx`, `_extract_pptx` удалены; `processor.py` импортирует новые `extract_docx`, `extract_xlsx`, `extract_pptx` и использует их в существующей диспетчеризации.
- Общий `test_extractors_office.py` пропускается в среде ассистента из-за отсутствия `ebooklib`; новые unit-тесты трех вынесенных форматов выполняются независимо от EPUB.
- Поведение и сигнатуры извлечения не менялись: `(data: bytes) -> str`.

## Проверки поставки 5 (принята пользователем)
- `python -m pytest -q` → пользователь сообщил: 75 passed, 5 deselected.
- `python -m pytest -q -m integration` → пользователь сообщил: 5 passed, 75 deselected.
- Запуск Uvicorn → Whisper small загружена; сервер завершён штатно.

## Проверки поставки 6
- `python -m pytest -q` → 59 passed, 8 skipped, 1 deselected.
- `python -m pytest -q -m integration` → 1 passed, 6 skipped, 61 deselected.
- `python -m compileall -q app.py backend tests` → успешно.
- Изолированные тесты ODT, ODS и ODP → успешно; проверены заголовки/абзацы, листы/строки/ячейки и слайды.
- Сравнение новой `extract_odf(data, kind)` с исходной `_extract_odf(data, kind)` из поставки 5 на одинаковых сгенерированных документах → точное совпадение для ODT (31 символ), ODS (62 символа), ODP (47 символов).
- ODF-импорты и реализации удалены из `processor.py`; маршрутизация трёх типов направлена на `extract_odf`.
- Основной набор пропускает интеграционные сценарии и тесты, требующие `ebooklib`/`striprtf`, отсутствующих в среде ассистента. ODF-библиотека `odfpy` доступна, отдельные тесты трёх форматов выполнены.
- Изменения поведения не планировались; тексты и порядок элементов совпали с предыдущей реализацией на тестовых документах.


## Проверки поставки 7
- `python -m pytest -q` → 62 passed, 9 skipped, 1 deselected.
- `python -m pytest -q -m integration` → 1 passed, 7 skipped, 64 deselected.
- `python -m compileall -q app.py backend tests` → успешно.
- FB2: изолированные тесты извлечения заголовков, абзацев и вложенного текста, отсутствующего body и ограничения результата → успешно.
- Сравнение `extract_fb2()` с прежней `_extract_fb2()` из поставки 6 на одном и том же тестовом документе → точное совпадение.
- EPUB: тестовый прогон на заглушке EbookLib проверил пропуск nav-документов, удаление script/style/nav и извлечение содержимого главы → успешно. Обычный тест с настоящим EbookLib пропущен, так как библиотека отсутствует в среде ассистента.
- `_extract_epub` и `_extract_fb2` удалены из `processor.py`; маршрутизация направлена в `extractors/epub.py` и `extractors/fb2.py`.
- Сигнатуры новых экстракторов сохранены: `(data: bytes) -> str`; используемый `limit_text` оставлен без изменений, включая добавление маркера обрезки.
- Изменений поведения не планировалось. Реальное чтение EPUB через EbookLib и общий end-to-end тест EPUB требуется подтвердить в среде пользователя.


## Проверки поставки 8
- `python -m compileall -q app.py backend tests` → успешно.
- `python -m pytest -q` → 73 passed, 7 skipped, 3 deselected.
- `python -m pytest -q -m integration` → 2 passed, 6 skipped, 75 deselected; интеграционный тест сканированного PDF с реальным Tesseract выполнен.
- Unit-тесты PDF: текстовый слой, OCR-путь на подставной странице, ограничение количества страниц → успешно.
- Unit-тесты DJVU: текстовый слой, OCR fallback, отсутствие инструментов, timeout/ошибка `djvutxt`, ограничение количества страниц, рендеринг и удаление TIFF после OCR → успешно.
- Сравнение `extract_pdf()` с прежней `_extract_pdf()` из поставки 7 на цифровом и сканированном PDF → точное совпадение (36 и 121 символ соответственно).
- Сравнение `extract_djvu()` с прежней `_extract_djvu()` на имитированных исполняемых файлах DjVuLibre для текстового слоя и OCR fallback → точное совпадение (15 и 56 символов).
- `processor.py` больше не содержит реализаций `_extract_pdf` и `_extract_djvu`; маршрутизация направлена в новые пакеты. Остальные форматы и цепочка `if/elif` не менялись (реестр и pipeline — этап A5).
- Таймауты DJVU сохранены: `djvutxt` — 60 с, `djvused` — 15 с, `ddjvu` для каждой страницы — 60 с; тексты ошибок сохранены. PDF по-прежнему использует `dpi=200`; защита размера рендера относится к B.5 и намеренно не включалась в структурный этап A4.
- Интеграционный DJVU-тест пропущен: в среде ассистента отсутствуют `c44`, `djvutxt`, `djvused` и `ddjvu`.
- Изменения HTTP-контракта и внешнего поведения не планировались.


## Проверки поставки 8 (принята пользователем)
- `python -m pytest -q` → пользователь сообщил: 95 passed, 5 deselected.
- `python -m pytest -q -m integration` → пользователь сообщил: 5 passed, 95 deselected.

## Проверки поставки 9
- `python -m compileall -q app.py backend tests` → успешно.
- Обычный `python -m pytest -q` в среде ассистента не собрал тесты: отсутствуют `EbookLib` и `striprtf`, а новый публичный пакет согласно A5 импортирует единый реестр экстракторов, включая эти зависимости.
- Контрольный pytest с кратковременными import-only заглушками только для отсутствующих `EbookLib` и `striprtf` (после импорта `backend.document_engine` заглушки удалены, поэтому format-specific тесты корректно пропускаются): 80 passed, 7 skipped, 3 deselected.
- Integration pytest в том же режиме: 2 passed, 6 skipped, 82 deselected.
- Тесты pipeline: 16 записей реестра, адаптеры ODT/ODS/ODP, диспетчеризация экстрактора, проверка ZIP до вызова экстрактора, ошибки пустого/неподдерживаемого документа, shim-совместимость и выполнение runner в рабочем потоке → успешно.
- Импорт `app.py`/Uvicorn в среде ассистента не выполнен: отсутствует `faster-whisper`; настоящий HTTP smoke-test остаётся проверкой пользователя.
- `app.py` переведён на импорт `from backend.document_engine import process_document`; тесты извлечения используют публичный импорт, прежний путь `backend.document_engine.processor` сохранён как shim.
- HTTP smoke-test через FastAPI TestClient с временными import-only заглушками отсутствующих библиотек (startup/lifespan не запускался): `POST /process-document` для TXT → 200 и контрактные поля `format`, `text`, `characters`.
- Поведение синхронного pipeline сохранено: прежняя последовательность пустой файл → размер → определение формата → проверка ZIP → экстрактор → `build_result`; `ZIP_FORMATS` и сообщения ошибок сохранены.
- Изменения HTTP-контракта и поведения извлечения не планировались.

## Поставка 10 — Whisper и HTTP-слой (A6 + A7)

### Что сделано
- Создан `backend/transcription/model.py` с `ModelHolder` (`load()`, `get()`, `is_loaded`) и единственным экземпляром `model_holder`.
- Управление моделью удалено из `app.py`; модель загружается в lifespan при запуске, а тяжёлая инициализация выполняется через `asyncio.to_thread`.
- `backend/transcription/service.py` переведён на публичную сигнатуру `transcribe_file(path)`. Сохранены параметры языка/beam/VAD, проверка длительности, ограничение параллельности и выполнение Whisper в рабочем потоке (меры B.3 из предыдущей поставки).
- Созданы `backend/api/health.py`, `transcribe.py`, `documents.py`, `schemas.py`; обработчики зарегистрированы через `register_routes()`.
- Создан `backend/main.py` с `create_app()` и `lifespan`; загрузка `.env` по явному пути происходит до импорта `settings`; сохранены проверка ключей, `umask 077`, подготовка закрытого временного каталога и очистка забытых аудиофайлов.
- Сохранён `BodySizeLimitMiddleware` с прежним пределом `max(MAX_DOCUMENT_SIZE, MAX_AUDIO_SIZE) + 1 MiB`.
- `app.py` сокращён до совместимой точки входа `from backend.main import app`.
- Добавлены схемы `TranscribeResponse` и `DocumentResponse` с именами полей, которые проверяет бот.
- Обновлены тесты: service использует model_holder, HTTP-тесты подменяют его модель, добавлены проверки ModelHolder и схем API.

### Проверки в среде ассистента
- `python -m compileall -q app.py backend tests` → успешно.
- Unit-набор с временными import-only заглушками EbookLib/striprtf исключительно для загрузки общего реестра (заглушки удалены до запуска pytest; зависящие от библиотек тесты пропускаются) → 84 passed, 8 skipped, 3 deselected.
- Integration-набор в том же режиме → 2 passed, 7 skipped, 86 deselected.
- Изолированные тесты `test_model_holder.py`, `test_transcription_service.py`, `test_api_schemas.py` → проверяются отдельно; их выполнение не требует импорта faster-whisper, поскольку импорт Whisper отложен до `ModelHolder.load()`.
- FastAPI TestClient smoke с временными import-only заглушками необязательных парсеров и подставной моделью: `/health` → 200; `/process-document` TXT → 200, поля `format/text/characters`; `/transcribe` → 200, поля `text/language/duration`.
- Lifespan smoke с подставной фабрикой модели → security check, временный каталог, очистка и `ModelHolder.load()` вызываются в указанном порядке; health после старта сообщает `loaded=true`.
- `@app.on_event` в исходниках больше не используется.

### Ограничения проверки
- В среде ассистента отсутствуют реальные `faster-whisper`, `EbookLib`, `striprtf`; настоящую модель Whisper и реальные EPUB/RTF-парсеры здесь не запускал. HTTP- и lifespan-smoke выполнены с тестовыми заглушками, не включёнными в архив.
- Пользовательская проверка с настоящей моделью, `.env` и установленными зависимостями требуется после распаковки.

### Изменения поведения
- HTTP-пути и JSON-поля не изменены.
- Жизненный цикл изменён штатно: модель больше не загружается через deprecated `@app.on_event`, а создаётся через FastAPI lifespan. Проверка ключей и подготовка temp storage происходят при старте приложения.
- `backend/api/__init__.py` импортирует router-модули внутри `register_routes()`, чтобы импортировать вспомогательные `backend.api.auth`/`middleware` независимо от сборки всего HTTP-приложения.
- Импорт `WhisperModel` отложен до `_build_model()`/старта сервиса, чтобы вспомогательные модули можно было импортировать в окружении без установленной модели; при реальном старте библиотека по-прежнему обязательна.


## Исправление поставки 10 — r2
- По traceback пользователя `tests/unit/test_api_lifespan.py::test_app_registers_all_expected_routes` падал с `AttributeError: '_IncludedRouter' object has no attribute 'path'` на используемой версии FastAPI/Starlette.
- Исправлен только тест регистрации маршрутов: вместо обхода внутренних объектов `app.routes` проверяется публичная OpenAPI-схема `app.openapi()["paths"]`, включая методы `GET /health`, `POST /transcribe` и `POST /process-document`. Производственный код и HTTP-контракт не менялись.
- Изменённые файлы r2: `tests/unit/test_api_lifespan.py`, `REFACTORING_LOG.md`.
- Целевой модуль `test_api_lifespan.py` с import-only заглушками отсутствующих в среде ассистента EbookLib/striprtf → 3 passed.
- Полный unit-набор с временными import-only заглушками только на этапе импорта реестра (зависимые от настоящих библиотек тесты пропускаются) → 84 passed, 8 skipped, 3 deselected.
- Integration-набор в том же режиме → 2 passed, 7 skipped, 86 deselected.
- `python -m compileall -q app.py backend tests` → успешно.
- Повторная проверка пользователем выполнена: 109 passed, 5 integration passed; Uvicorn и загрузка Whisper small успешны. Исправление r2 принято.

## Поставка 10 (A6 + A7) — принята пользователем
- Пользователь сообщил: `python -m pytest -q` → 109 passed, 5 deselected.
- Пользователь сообщил: `python -m pytest -q -m integration` → 5 passed, 109 deselected.
- Uvicorn запущен; Whisper small успешно загружена; `/health` → `{"status":"ok","model":"small","loaded":true}`; сервер завершён штатно.
- Исправление r2 проверки маршрутов через публичную OpenAPI-схему принято.

## Поставка 11 — финальная чистка (A8)

### Что сделано
- Удалён `backend/document_engine/processor.py` — временный совместимый shim после завершения A5/A7.
- Удалены импорт и проверка shim из `tests/unit/test_document_engine_pipeline.py`; добавлена проверка отсутствия файла.
- Обновлён комментарий `tests/unit/test_extractors_text.py`: причина пропуска связанных с EPUB/RTF тестов теперь описывает импорт общего публичного реестра, а не уже удалённый `processor.py`.
- Проверено отсутствие `test_*.py` в корне, а также каталогов `test_documents/` и `uploads/`. Эти старые элементы уже отсутствовали в исходном архиве delivery-10-r2; в этой поставке повторно подтверждено, что они не попали в целевой проект.
- Добавлены `tests/unit/test_architecture_boundaries.py`: проверяется, что Document Engine не зависит от API/transcription/config, API не становится зависимостью нижних слоёв, а `errors`, `common` и `config` не импортируют другие прикладные пакеты.
- Проведён аудит всех модулей `backend/`: добавлены недостающие модульные docstrings, описания публичных функций/классов и недостающие аннотации типов в соответствии с C.1. Поведение обработчиков не менялось.
- Добавлены `docs/architecture.md` и `docs/architecture.ru.md` с актуальными потоками API, startup/lifespan, Whisper, Document Engine, границами пакетов и существующими ограничениями.
- README, API reference, operations guide, adding-a-format, security checklist и deploy-примеры остаются в отдельной поставке документации (часть C, поставка 13 согласно таблице плана); в этой поставке их содержание не дублируется.
- Исправлена аннотация `check_security_settings` на публичный тип `Settings` из `backend.config`. При этом сохранены реэкспорты `Settings`/`settings` из `backend/config/__init__.py` и публичных классов из `backend/errors/__init__.py`.
- Обновлён журнал поставок; статус поставки 10 изменён на «принято» по результатам пользователя.

### Проверки в среде ассистента
- `python -m compileall -q app.py backend tests` → успешно.
- Unit-набор с кратковременными import-only заглушками `EbookLib` и `striprtf` исключительно для импорта общего реестра (заглушки удаляются до запуска pytest; тесты реальных отсутствующих парсеров пропускаются) → 90 passed, 8 skipped, 3 deselected.
- Integration-набор в том же режиме → 2 passed, 7 skipped, 92 deselected.
- AST-аудит модулей: отсутствующих модульных docstrings, публичных docstrings и аннотаций функций не найдено; внутренние вложенные callbacks/helpers не считаются публичными API.
- Проверка границ импортов (unit-тесты) → успешно.
- Проверено отсутствие `backend/document_engine/processor.py`, корневых `test_*.py`, `test_documents/` и `uploads/`; проверено наличие обеих architecture-документаций.

### Ограничения и отклонения
- В исходном архиве delivery-10-r2 не было корневых `test_*.py`, `test_documents/` или `uploads/`, поэтому фактически удалён только shim `processor.py`; отсутствие прочих старых элементов подтверждено проверкой.
- Настоящие `EbookLib` и `striprtf` в среде ассистента отсутствуют. Тесты зависящих от них парсеров пропускались; пользовательская среда с полным `requirements-lock.txt` остаётся эталоном этих проверок.
- Полный пакет документации C.2 и файлы развёртывания не создавались преждевременно: по таблице поставок плана они входят в отдельную поставку документации.
- Изменения поведения HTTP API и извлечения документов не вносились.



## Поставка 12 — очереди и сроки (B.4 + B.13)

### Что сделано
- Реализован `Deadline` на `time.monotonic()` с методами `remaining()` и `check()`; единый 180-секундный срок создаётся при старте обработки документа после получения рабочего слота.
- `process_document_sync(data, filename, max_characters=None, deadline=None)` принимает общий deadline. Проверки добавлены перед/после ключевых этапов pipeline и в циклы PDF, DJVU/OCR, XLSX, PPTX, ODT/ODS/ODP. Для OCR timeout одной страницы ограничен также остатком общего срока.
- Реализован `run_limited()` для внешних программ: запуск списком аргументов без shell, ограничение stdout, timeout с принудительным завершением процесса, stderr во временном файле и ограниченный preview. Перевод текущих вызовов DJVU на этот runner относится к шагу B.9.
- Реализован общий `WorkQueue`: максимум N активных задач и заданное число ожидающих; корректно учитываются отменённые ожидающие задачи, есть проверка `is_full()`.
- Document Engine использует очередь 2 активных + 4 ожидающих; Whisper — 1 активная + 4 ожидающих по умолчанию. Добавлены `MAX_WAITING_DOCUMENTS` и `MAX_WAITING_TRANSCRIPTIONS` в настройки и `.env.example`.
- API резервирует место в очереди до копирования документа в память и до сохранения аудио в private temp storage. Седьмой запрос при 2+4 занятой очереди документов и шестой при 1+4 занятой очереди транскрибации быстро получают 503.
- Добавлен `ServerBusyError` (503, `Retry-After: 30`) и общий обработчик `BackendError`; `ProcessingTimeoutError` возвращается как HTTP 504.
- При отмене HTTP-корутины worker thread не теряет слот очереди до фактического завершения: `asyncio.to_thread` защищён через `asyncio.shield` и ожидание завершения потока.
- Добавлены тесты deadline, subprocess runner, WorkQueue, HTTP заголовка `Retry-After` и отклонения до прикладного чтения/копирования upload.

### Файлы
- Созданы: `backend/common/work_queue.py`, `backend/api/error_handlers.py`, `tests/unit/test_deadline.py`, `tests/unit/test_subprocess_runner.py`, `tests/unit/test_work_queue.py`, `tests/unit/test_api_work_queue.py`.
- Изменены: `.env.example`, `backend/common/deadline.py`, `backend/common/subprocess_runner.py`, `backend/config/settings.py`, `backend/document_engine/__init__.py`, `backend/document_engine/pipeline.py`, `backend/document_engine/runner.py`, `backend/document_engine/extractors/__init__.py`, PDF/DJVU/XLSX/PPTX/ODF extractors, OCR package, `backend/errors/base.py`, `backend/errors/__init__.py`, `backend/transcription/service.py`, API `documents.py`/`transcribe.py`, `backend/main.py`, связанные unit-тесты и этот журнал.
- Удалённые файлы: нет. Перемещения: нет.

### Изменения поведения
- Одновременная обработка по-прежнему ограничена существующими worker-лимитами, но очередь ожидания теперь конечная. При её заполнении API сразу отвечает `503` с `Retry-After: 30`, без чтения upload в коде приложения и без копирования в аудиохранилище.
- Обработка документов теперь ограничена общим дедлайном 180 секунд; истечение срока даёт HTTP 504 с безопасным текстом.
- HTTP-маршруты, multipart-поле `file` и поля JSON-ответов не изменены.

### Проверки в среде ассистента
- `python -m compileall -q app.py backend tests` → успешно.
- Unit-набор с временными import-only заглушками EbookLib/striprtf только для загрузки общего реестра (заглушки удалены до pytest) → 103 passed, 8 skipped, 3 deselected.
- Integration-набор в том же режиме → 2 passed, 7 skipped, 105 deselected.
- Новые тесты: общая очередь, предел рабочих/ожидающих задач, 503/`Retry-After`, раннее отклонение документа и аудио, deadline, принудительное завершение timed-out subprocess и ограничение stdout → успешно.
- Архитектурные тесты границ импортов → успешно: `common` не импортирует `errors`; используемые исключения очередей/deadline/subprocess нейтральны, а преобразование к `BackendError` выполняется на уровне application/service.

### Ограничения и отклонения
- В среде ассистента отсутствуют `faster-whisper`, `EbookLib` и `striprtf`; поэтому настоящая загрузка Whisper и end-to-end парсинг EPUB/RTF не запускались. Tesseract установлен, но средства DjVuLibre отсутствуют; 7 интеграционных тестов пропущены средой.
- В отличие от примеров B.4/B.13, `common` не импортирует `backend.errors`: это сохранило принятую в поставке 11 границу архитектуры (`errors`, `common`, `config` независимы друг от друга). `DeadlineExceededError`, `QueueFullError` и ошибки `run_limited` — нейтральные исключения; pipeline/application слой переводит их в безопасные ошибки API. WorkQueue получает `ServerBusyError` фабрикой исключений.
- Вместо неатомарной проверки `is_full()` отдельно от чтения файла API входит в `async with queue.slot()` перед чтением/копированием upload. Это атомарно резервирует место и исключает гонку между предварительной проверкой и фактическим помещением задачи в очередь.
- `run_limited()` добавлен и покрыт unit-тестами, но текущие DJVU вызовы будут переведены на него в поставке B.9 (плановая поставка лимитов документов).
- `max_characters` добавлен в сигнатуру синхронного pipeline как совместимый параметр для B.7; реальное ограничение текста будет реализовано в поставке лимитов документов.

### Что проверить пользователю
1. `python -m pytest -q` и `python -m pytest -q -m integration` в окружении с полным `requirements-lock.txt`.
2. Отправить одновременно 10 документов; ожидаются максимум 2 активных, 4 ожидающих, остальные — HTTP 503 с `Retry-After: 30`.
3. Подтвердить, что `/health` отвечает во время обработки; аналогично проверить переполнение очереди транскрибации (1 активная + 4 ожидающих по умолчанию).
4. На тестовом документе/подставном экстракторе установить дедлайн в прошлом и проверить HTTP 504; обычные PDF/Office/ODF документы должны продолжать обрабатываться.


## Проверки поставки 12 (принята пользователем)
- `python -m pytest -q` → пользователь сообщил: 128 passed, 5 deselected.
- `python -m pytest -q -m integration` → пользователь сообщил: 5 passed, 128 deselected.
- Запуск Uvicorn → Whisper small загружена; `/health` → 200.

## Проверки поставки 13 (в среде ассистента)
- `python -m compileall -q app.py backend tests` → успешно.
- Основной набор через bootstrap-скрипт, временно подменяющий отсутствующие optional-пакеты только для первичного импорта → 118 passed, 8 skipped, 3 deselected.
- Integration через тот же bootstrap → 2 passed, 7 skipped, 120 deselected; сканированный PDF/OCR прошёл, DJVU пропущен из-за отсутствующих `c44`, `djvutxt`, `djvused`, `ddjvu`.
- Дополнительные unit-тесты: PDF DPI, общая длина текста, `max_characters`, `truncated`, XLSX/ODS row-column caps, OCR dimensions/cache, DJVU output/file size и render args.
- Настоящая загрузка Whisper, EPUB/RTF с их библиотеками и DjVuLibre не выполнялись в этой среде.

## Поставка 13 — лимиты документов (B.5 + B.7 + B.8 + B.9)

### Что сделано
- PDF: добавлен расчёт `_render_dpi(page)`, который выбирает максимально возможное разрешение до рендера в пределах `MAX_IMAGE_PIXELS`; если страница не помещается в лимит даже при `PDF_OCR_MIN_DPI`, документ отклоняется.
- Добавлены `TextBudget` и `ExtractContext`. Все экстракторы получают общий бюджет и дедлайн; повторный `sum(map(len, result))` удалён. Бюджет учитывает разделители между фрагментами, поэтому итоговый `text` не превышает лимит.
- Добавлены ограничения таблиц: XLSX/ODS — максимум 100 000 строк и 256 столбцов; XLSX открывается в read-only режиме и ограничивает диапазон `iter_rows`, ODS перебирает строки и ячейки лениво.
- В API `/process-document` добавлено необязательное multipart-поле `max_characters`. Оно может только уменьшить серверный лимит. Ответ дополнен совместимым полем `truncated`; старые запросы без `max_characters` остаются допустимы.
- PPTX, EPUB и CSV перешли на инкрементальный бюджет; DOCX, ODT, ODP, FB2, HTML, XML, RTF, TXT/MD, PDF и DJVU также используют общий контекст, прерывая циклы, когда лимит исчерпан.
- OCR проверяет `width * height` до `image.copy()`. `ensure_ready(languages)` кэширует успешные проверки Tesseract и языковых данных (`lru_cache(maxsize=8)`); отсутствующие бинарник/языки возвращают безопасную `DependencyMissingError` (503).
- DJVU: все вызовы `djvutxt`, `djvused`, `ddjvu` используют `run_limited`; вывод `djvutxt` ограничен `MAX_EXTRACTED_TEXT_LENGTH * 4`, timeout учитывает остаток общего deadline; добавлены ограничение рендера `-size=3500x3500` и проверка TIFF-файла до OCR (`MAX_DJVU_PAGE_BYTES=100 MiB`). `stderr` сохраняется только в серверный лог, клиент получает безопасные сообщения.

### Файлы
- Созданы: `backend/document_engine/extractors/base.py`, `tests/unit/test_api_character_budget.py`, `tests/unit/test_extraction_budget_limits.py`, `tests/unit/test_ocr_limits.py`, `tests/unit/test_text_budget.py`.
- Изменены: `REFACTORING_LOG.md`, `backend/api/documents.py`, `backend/api/schemas.py`, `backend/common/text_budget.py`, реестр и экстракторы `backend/document_engine/extractors/` (включая PDF, DJVU, Office, ODF и текстовые форматы), `backend/document_engine/limits.py`, OCR-модули, `backend/document_engine/pipeline.py`, `backend/document_engine/result.py`, а также связанные тесты API, pipeline и экстракторов.
- Удалённые файлы: нет. Перемещения: нет.

### Изменения поведения
- Добавлено необязательное поле запроса `max_characters`; при его отсутствии прежнее поведение запроса сохраняется с серверным лимитом.
- В JSON результата добавлено поле `truncated` (по умолчанию `false` для совместимости схемы); `characters` соответствует фактической длине возвращённого текста.
- Страницы PDF с чрезмерными размерами отклоняются до рендера; большие кадры OCR отклоняются до копирования; OCR-проверки Tesseract/языков кэшируются.
- DJVU-команды ограничены по времени и выводу; чрезмерный TIFF отклоняется до чтения в память.

### Проверки в среде ассистента
- `python -m compileall -q app.py backend tests` → успешно.
- Полный unit-набор через bootstrap-скрипт: временные import-only заглушки `EbookLib`/`striprtf` используются только для первичного импорта общего реестра и удаляются до старта pytest → 118 passed, 8 skipped, 3 deselected.
- Полный integration-набор в том же режиме → 2 passed, 7 skipped, 120 deselected. PDF/OCR integration passed.
- Дополнительные тесты проверяют PDF DPI, `TextBudget`, `max_characters`, `truncated`, ограничения XLSX/ODS, проверку размеров и кэш OCR, лимиты DJVU stdout/TIFF и параметры рендера.
- Проверено: в DJVU-пакете не осталось `subprocess.run`, `capture_output=True` или утечки `stderr[:500]`; в экстракторах нет `sum(map(len, ...))`.

### Ограничения и отклонения
- В среде ассистента отсутствуют `EbookLib`, `striprtf` и утилиты DjVuLibre (`c44`, `djvutxt`, `djvused`, `ddjvu`), поэтому связанные парсерные тесты пропущены, а реальная интеграция DJVU не выполнена. Настоящий faster-whisper в этой среде также не загружался. Пользовательская среда с полным lock-файлом остаётся эталоном.
- Для ODS введён ленивый обход узлов таблицы вместо предварительного создания полного списка строк; это необходимо, чтобы лимиты строк/столбцов применялись до материализации большого диапазона.
- Маркер текста `…[truncated]` в результате не добавляется: он сам мог бы превысить заданный клиентом максимум. Факт обрезки сообщается отдельным полем `truncated`.

### Что проверить пользователю
1. Запустить `python -m pytest -q` и `python -m pytest -q -m integration` в полном рабочем окружении.
2. Отправить длинный текстовый документ с `max_characters=500`; проверить `characters <= 500` и `truncated=true`. Повторить тот же запрос без поля и подтвердить совместимость старого клиента.
3. Проверить сканированный PDF обычного размера и большой тестовый PDF; проверить XLSX/ODS с большими и разреженными диапазонами.
4. Проверить OCR сканированного PDF: повторные запросы не должны каждый раз запускать `tesseract --list-langs`. Проверить отсутствующий язык на тестовом окружении → безопасный 503.
5. На машине с DjVuLibre проверить текстовый и сканированный DJVU, а также что отказ внешней команды не раскрывает `stderr` клиенту.

Статус: готово в среде ассистента; ожидает проверки пользователя.


## Поставка 13 (принята пользователем)
- `python -m pytest -q` → пользователь сообщил: 143 passed, 5 deselected.
- `python -m pytest -q -m integration` → пользователь сообщил: 5 passed, 143 deselected.

## Поставка 14 — XML, ошибки и зависимости (B.10 + B.11 + B.12)

### Что сделано
- Создан `backend/document_engine/guards/xml_safe.py` на базе `defusedxml.ElementTree`. Парсер явно запрещает DTD, сущности и внешние сущности; синтаксически некорректный XML преобразуется в безопасный `DocumentRejectedError`.
- `extractors/fb2.py` и `extractors/xml_text.py` переведены на общий безопасный XML-парсер.
- В pipeline собственные ошибки пустого/слишком большого/неподдерживаемого документа переведены в типизированные ошибки `BackendError`. Ошибки проверки ZIP нормализуются до общего безопасного отказа; непредвиденные исключения экстракторов логируются с кодом формата и возвращают общий `DocumentRejectedError` без текста библиотеки.
- HTTP error handlers дополнены общим обработчиком непредвиденных исключений: клиент получает `Internal server error`, технические подробности остаются только в серверном логе. Типизированные ошибки продолжают возвращать их безопасное сообщение, код и headers (включая `Retry-After`).
- API документов больше не отдаёт `str(ValueError)` клиенту. Собственные ошибки обрабатываются как типизированные; имя файла очищается через `log_safe()` перед записью в лог.
- Добавлены настройки `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`, `WHISPER_MODEL_PATH`, `WHISPER_OFFLINE`, `ENABLE_DOCS` и примеры всех значений в `.env.example`.
- Swagger `/docs` и схема `/openapi.json` выключены по умолчанию; включаются через `ENABLE_DOCS=true`. ReDoc остаётся отключён.
- WhisperModel получает путь модели (либо `WHISPER_MODEL_SIZE`), выбранные `device`/`compute_type`/`cpu_threads` и `local_files_only=WHISPER_OFFLINE`.
- Из `requirements.txt` удалены неиспользуемые `aiohttp` и `pypdf`; добавлен `defusedxml`; версии библиотек чтения пользовательских файлов ограничены интервалом до следующей мажорной версии по значениям из lock-файла. Из `requirements-lock.txt` удалены неиспользуемые `pymupdf4llm` и `pymupdf_layout`.

### Файлы
- Созданы: `backend/document_engine/guards/xml_safe.py`, `tests/unit/test_xml_safe.py`, `tests/unit/test_api_errors.py`, `tests/unit/test_api_docs_visibility.py`, `tests/unit/test_whisper_model_settings.py`.
- Изменены: `.env.example`, `REFACTORING_LOG.md`, `requirements.txt`, `requirements-lock.txt`, `backend/api/documents.py`, `backend/api/error_handlers.py`, `backend/config/settings.py`, `backend/main.py`, `backend/transcription/model.py`, `backend/document_engine/pipeline.py`, `backend/document_engine/extractors/fb2.py`, `backend/document_engine/extractors/xml_text.py`, PDF/OCR проверки собственных ошибок и связанные unit-тесты.
- Удалённые файлы: нет. Перемещения: нет.

### Изменения поведения
- FB2/XML с DTD или entity declarations отклоняются; некорректный XML не раскрывает низкоуровневые parser errors.
- Клиент получает только заранее определённые сообщения ошибок; неожиданные исключения возвращают HTTP 500 с `Internal server error`, а ошибка чтения/разбора документа — общий безопасный отказ 400.
- Имя файла нормализуется перед логированием; переносы строк не могут создать поддельные log records.
- `/docs` и `/openapi.json` отключены по умолчанию; для локальной разработки включаются `ENABLE_DOCS=true`.
- Устройство/тип вычислений Whisper и путь модели вынесены в настройки; `WHISPER_OFFLINE=true` запрещает скачивание модели из Hugging Face и позволяет использовать локальную модель или кэш.
- Форматы успешных HTTP-ответов и маршруты не изменились.

### Проверки в среде ассистента
- `python -m compileall -q app.py backend tests` → успешно.
- Unit-набор через bootstrap временных import-only заглушек `EbookLib`/`striprtf` только при первоначальном импорте реестра (заглушки удаляются до pytest) → 129 passed, 8 skipped, 3 deselected.
- Integration-набор в том же режиме → 2 passed, 7 skipped, 131 deselected.
- Тесты XML: обычный XML проходит; DTD, entity declarations и malformed XML отклоняются; FB2 и XML экстракторы используют безопасный parser.
- Тесты B.11: неожиданные ошибки API не раскрывают исключение/путь клиенту; ошибки экстракторов преобразуются в общий безопасный отказ; filename проверяется на log injection.
- Тесты B.12: `/docs` и `/openapi.json` выключены/включаются настройкой; фабрика Whisper передаёт устройство, compute type, локальный путь и offline flag.
- Статическая проверка зависимостей: `aiohttp`/`pypdf` отсутствуют в `requirements.txt`; `defusedxml` присутствует в requirements и lock; `pymupdf4llm`/`pymupdf_layout` отсутствуют в lock.

### Ограничения и отклонения
- В среде ассистента отсутствуют `EbookLib`, `striprtf`, `faster-whisper` и DjVuLibre; соответствующие тесты пропускались. Настоящую загрузку Whisper (в том числе в офлайн-режиме) здесь не запускал; проверено только то, какие аргументы передаются в `WhisperModel`.
- Реальная проверка отключения сетевого скачивания модели должна быть выполнена пользователем на сервере с локальной моделью и `WHISPER_OFFLINE=true`.
- В multipart-тесте Starlette сам экранирует LF в имени файла как `%0A`; дополнительная очистка `log_safe()` оставлена как защита для любых других путей логирования.

### Что проверить пользователю
1. `python -m pytest -q` и `python -m pytest -q -m integration` в полном окружении.
2. Отправить XML и FB2 с `DOCTYPE`/`ENTITY`: ожидается отказ 400 без парсерных подробностей. Обычные XML/FB2 должны обрабатываться.
3. Отправить повреждённый DOCX/ZIP и документ с некорректным содержимым: тело ответа должно содержать только безопасное описание ошибки.
4. В `.env` указать `WHISPER_MODEL_PATH` на заранее подготовленную модель, `WHISPER_OFFLINE=true`, затем запустить сервер без доступа к Hugging Face. Проверить успешную загрузку. Не записывать реальные ключи в отчёт.
5. Проверить, что `/docs` и `/openapi.json` возвращают 404 по умолчанию; `ENABLE_DOCS=true` использовать только в доверенной среде разработки.

## Поставка 14 (принята пользователем)
- Пользователь подтвердил: `python -m pytest -q` → 154 passed, 5 deselected; `python -m pytest -q -m integration` → 5 passed, 154 deselected.
- Uvicorn загрузил Whisper `small`; `/docs` и `/openapi.json` вернули `404`; сервер завершился штатно.
- Каталог проверки подтверждён: `/home/zelensky/whisper-server-delivery-14/whisper-server`.

## Поставка 15 — документация, развёртывание и журналы (часть C + D.1.3, D.1.4, D.2.2 п. 5, D.3.1, D.5.2)

### Что сделано
- Добавлены `README.md` (английский) и `README.ru.md` (русский): назначение, поддерживаемые форматы, установка системных программ и Python-зависимостей, быстрый старт, все переменные окружения с default values, проверка curl, тесты и ссылки на документацию.
- Переписаны оба файла архитектуры: потоки запросов, startup/lifespan, HTTP-слой, Whisper/offline, Document Engine, ограничения и границы безопасности, Request ID/SecretsFilter, дерево проекта.
- Добавлены `docs/api.md` (контракт Telegram-клиента и новые поля/заголовки), `docs/operations.md` (установка, права, локальная модель Whisper, `/health`, `/ready`, журнал, troubleshooting, обновления, rollback), `docs/adding-a-format.md` (рецепт из 5 шагов) и `docs/security-checklist.md` (24 пункта D.8).
- Добавлен `GET /ready`, защищённый `DOCUMENT_API_KEY`. Он сообщает наличие Tesseract, доступные языки, наличие всех трёх утилит DjVuLibre и состояние Whisper; диагностика не пытается автоматически устанавливать зависимости.
- Добавлен `backend/common/request_id.py`: проверка `X-Request-ID` по `[A-Za-z0-9._-]{8,64}`, генерация UUID при отсутствии/некорректном значении, ответный заголовок и `RequestIdFilter`.
- Добавлен `backend/common/log_filters.py` (`SecretsFilter`): редактирование заданных Whisper/Document API keys, token-like строк и Bearer-значений в log messages/tracebacks.
- `backend/common/logging_setup.py` теперь устанавливает формат с request ID и оба фильтра на root handlers. В `backend/main.py` подключены фильтры, request-ID middleware и новый router. Request-ID middleware стоит внешним относительно body-size middleware, чтобы ID возвращался даже для раннего отказа по размеру запроса.
- Добавлены примеры `systemd`, UFW, nginx HTTPS и WireGuard для обеих машин в `deploy/`, все адреса/ключи/сертификаты — placeholders; добавлено руководство по применению.
- По C.1 добавлены docstrings для оставшихся публичных функций и внутренних ASGI/filter helper-методов, которые были без описаний.

### Файлы
- Созданы: `README.md`, `README.ru.md`, `docs/api.md`, `docs/operations.md`, `docs/adding-a-format.md`, `docs/security-checklist.md`, `deploy/README.md`, `deploy/media-backend.service.example`, `deploy/ufw-rules.sh.example`, `deploy/nginx.conf.example`, `deploy/wireguard-backend.conf.example`, `deploy/wireguard-bot.conf.example`, `backend/api/ready.py`, `backend/common/request_id.py`, `backend/common/log_filters.py`, `tests/unit/test_api_ready.py`, `tests/unit/test_request_id_logging.py`.
- Изменены: `docs/architecture.md`, `docs/architecture.ru.md`, `backend/api/__init__.py`, `backend/main.py`, `backend/common/logging_setup.py`, `backend/api/auth.py`, `backend/api/middleware.py`, `backend/common/subprocess_runner.py`, `backend/document_engine/extractors/__init__.py`, `tests/unit/test_api_lifespan.py`, `REFACTORING_LOG.md`.
- Удалённые файлы: нет. Перемещения: нет. Архив бота не изменялся.

### Изменения поведения
- Добавлен диагностический `/ready` с отдельной авторизацией Document API key; `/health` и существующие POST-маршруты не изменены.
- В ответы добавляется `X-Request-ID`; принимаемый ID валидируется, некорректный заменяется UUID.
- Логи получают request ID; настроенные ключи и token-like/Bearer values редактируются до вывода в root handlers.
- Конфигурация, обработка документов, формат успешных ответов и авторизация прежних endpoints остаются совместимыми с ботом.

### Проверки в среде ассистента
- `python -m compileall -q app.py backend tests` → успешно.
- Unit-набор через внешний bootstrap с временными import-only stub для отсутствующих в среде `EbookLib` и `striprtf` (stubs удалены до pytest) → 136 passed, 8 skipped, 3 deselected.
- Integration-набор тем же способом → 2 passed, 7 skipped, 138 deselected.
- Новые unit-тесты проверяют авторизацию/содержимое `/ready`, отсутствующие native tools, принятие/замену `X-Request-ID`, присвоение ID в log records, редактирование секретов и traceback, подключение logging filters.
- TestClient smoke с подменённым `model_holder.load` (в среде нет `faster-whisper`) → `/ready` 200 с `DOCUMENT_API_KEY`, валидный ID возвращён в `X-Request-ID`, `/health` 200, `/docs` и `/openapi.json` 404.

### Ограничения и отклонения
- В окружении ассистента отсутствуют `EbookLib`, `striprtf` и утилиты DjVuLibre. Связанные тесты пропущены; реальную EPUB/RTF/DJVU-интеграцию здесь не запускал. Bootstrap используется только для импорта общего реестра во время сбора тестов; его модули не входят в проект и удаляются до pytest.
- `systemd`, UFW, nginx и WireGuard templates не применялись на реальном сервере. Адреса, пути, ресурсы, сертификаты и SSH allow-list должны быть заменены и проверены владельцем инфраструктуры.
- `/ready` реализует диагностику по пункту C.5; она не меняет статус HTTP на 503 при отсутствующем parser tool, а возвращает диагностические boolean/list поля, как задано в плане.

### Что проверить пользователю
1. Запустить `python -m pytest -q` и `python -m pytest -q -m integration` в полном окружении.
2. Проверить `/ready` без ключа (401 при заданном `DOCUMENT_API_KEY`) и с ключом; сверить поля `tesseract`, `languages`, `djvulibre`, `model_loaded`.
3. Послать валидный `X-Request-ID` и проверить такой же ответный заголовок; затем передать недопустимый ID и проверить, что backend возвращает новый UUID. По ID найти строки в серверном логе.
4. На тестовой машине применить systemd/firewall/VPN или TLS-пример после замены всех placeholders. Проверить, что не потерян доступ администратора по SSH, код не доступен сервисному пользователю на запись, сервису доступна только временная папка, а egress-политика совместима с локальной моделью.
5. Выполнить security checklist `docs/security-checklist.md`; не считать шаблоны развёртывания автоматически применёнными.

Статус: готово в среде ассистента; ожидает проверки пользователя.

## Поставка 16 — финальная приёмка (аудит B.0, контрактов и D.8)

### Что сделано
- Повторно сверены все 18 находок BE-01…BE-18 из B.0 с кодом `backend/`, тестами и deployment templates.
- Обновлена таблица поставок: поставки 14 и 15 отмечены принятыми на основании сообщений пользователя; поставка 16 ожидает его финальной проверки.
- В `backend/api/documents.py` удалён недостижимый `except BackendError`: теперь типизированные ошибки документа действительно попадают в warning-лог с очищенным именем файла и затем передаются стандартному HTTP error handler.
- Добавлен тест `test_typed_document_rejection_is_logged_without_raw_filename`.
- Из `requirements-lock.txt` удалены `aiohttp`, `pypdf` и оставшиеся только от `aiohttp` lock-only зависимости `aiohappyeyeballs`, `aiosignal`, `frozenlist`, `multidict`, `propcache`, `yarl`; прямые зависимости проекта сверены с lock-файлом.
- Создан `docs/final-acceptance.md`: матрица BE-01…BE-18 и отдельная оценка каждого из 24 пунктов D.8 с разделением подтверждённых, покрытых тестами и открытых инфраструктурных проверок.
- Обновлён раздел принятых решений/отклонений: `request_id.py` и `log_filters.py` реализованы в поставке 15, а не оставлены на последующий этап.

### Проверки в среде ассистента
- `python -m compileall -q app.py backend tests` → успешно.
- Unit pytest через внешний import-only bootstrap для отсутствующих `EbookLib`/`striprtf` → 137 passed, 8 skipped, 3 deselected.
- Integration pytest тем же способом → 2 passed, 7 skipped, 139 deselected.
- `sh -n deploy/ufw-rules.sh.example` → успешно.
- AST-аудит 71 модуля `backend/`: module/public docstrings отсутствуют не были; одна вложенная callback `adapted` не имеет type annotation для одного аргумента, что не относится к публичному API.
- Поиск `shell=True`, `eval`, `exec`, `pickle`, SQL/ORM в исходниках backend → совпадений не найдено.
- Проверка файлов и архива: все ожидаемые README/docs/deploy examples присутствуют; `.env`, кэши и временные файлы исключены при упаковке.

### Проверки пользователя, учтённые при финальном аудите
- Поставка 14: 154 passed, 5 deselected; 5 integration passed; Whisper small загрузилась; `/docs` и `/openapi.json` вернули 404; каталог `delivery-14` подтверждён.
- Поставка 15: 161 passed, 5 deselected; 5 integration passed; `/ready` с ключом вернул 200 и показал `tesseract=true`, `languages=[eng, osd, rus]`, `djvulibre=true`, `model_loaded=true`; запуск/остановка Uvicorn успешны.
- В логах запуска Whisper был запрос к `huggingface.co`; поэтому D.8.13 (модель без сети при `WHISPER_OFFLINE=true`) не отмечается выполненным.
- Пользователь подтвердил `/docs` и `/openapi.json` → 404. Фактическая сеть, systemd, права файлов, egress, шифрование дисков и bot allow-list не проверялись в этой поставке.

### Открытые эксплуатационные пункты
- D.8.1–4, 7–15, 17–24 остаются полностью или частично пользовательскими проверками на A/B; D.8.16 подтверждён пользователем.
- D.8.5–6 подтверждены кодом/автотестами и проверкой ключа у `/ready`; повторить exact `POST /process-document` 401/200 на машине B перед production.
- Пункты D.8.17–19 имеют соответствующее покрытие тестами, но требуют проверки реального journald, oversized upload и нагрузочного запуска 10 документов.
- BE-17: application admission queue реализована; systemd resource controls и сетевой egress являются только шаблоном до применения.
- BE-18: приватная сеть, VPN/TLS, UFW и фактическая изоляция портов не могут быть подтверждены архивом.

### Итог
Кодовая часть и артефакты плана собраны; HTTP-контракт с ботом сохранён. Финальная эксплуатационная готовность не сертифицирована до закрытия оставшихся пунктов D.8. Подробная матрица находится в `docs/final-acceptance.md`.

Статус: готово, ожидает финального подтверждения пользователя.
