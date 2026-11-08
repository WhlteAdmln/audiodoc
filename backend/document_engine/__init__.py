"""Публичный интерфейс Document Engine."""

from backend.document_engine.pipeline import process_document_sync
from backend.document_engine.runner import document_queue, process_document

__all__ = ["document_queue", "process_document", "process_document_sync"]
