"""Общая конфигурация тестов бэкенда.

Переменные окружения задаются до импорта app и document_engine: настройки
приложения читаются при импорте модулей.
"""

import os

os.environ.setdefault("ALLOW_UNAUTHENTICATED", "true")
os.environ.setdefault("WHISPER_API_KEY", "")
os.environ.setdefault("DOCUMENT_API_KEY", "")
os.environ.setdefault("LOG_LEVEL", "WARNING")
