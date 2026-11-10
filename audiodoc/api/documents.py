# Copyright (c) 2026 Nikolai Zelensky
"""Document text extraction endpoint."""

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from audiodoc.api.auth import require_key
from audiodoc.api.dependencies import get_document_queue
from audiodoc.api.schemas import DocumentResponse, ErrorResponse
from audiodoc.common.limited_upload import read_upload_limited
from audiodoc.common.safe_log import log_safe
from audiodoc.common.work_queue import WorkQueue
from audiodoc.document_engine import process_document
from audiodoc.document_engine.limits import (
    MAX_DOCUMENT_SIZE,
    MAX_EXTRACTED_TEXT_LENGTH,
)
from audiodoc.document_engine.result import DocumentResult
from audiodoc.errors.base import BackendError

logger = logging.getLogger(__name__)

router = APIRouter(
    dependencies=[
        Depends(
            require_key(
                lambda configured_settings: configured_settings.AUDIODOC_DOCUMENT_KEY
            )
        )
    ]
)


@router.post(
    "/process-document",
    response_model=DocumentResponse,
    responses={
        400: {
            "model": ErrorResponse,
            "description": (
                "The document was rejected or uses an unsupported format "
                "(document_rejected, unsupported_format)."
            ),
        },
        413: {
            "model": ErrorResponse,
            "description": (
                "The document payload exceeds the processing limit (payload_too_large)."
            ),
        },
        500: {
            "model": ErrorResponse,
            "description": "Unexpected internal failure (internal_error).",
        },
        503: {
            "model": ErrorResponse,
            "description": (
                "A required dependency is missing (dependency_missing), "
                "or the work queue is full (server_busy)."
            ),
            "headers": {
                "Retry-After": {
                    "description": "Seconds to wait before retrying.",
                    "schema": {"type": "string"},
                }
            },
        },
        504: {
            "model": ErrorResponse,
            "description": "Document processing timed out (processing_timeout).",
        },
    },
)
async def process_document_endpoint(
    file: Annotated[UploadFile, File()],
    queue: Annotated[WorkQueue, Depends(get_document_queue)],
    max_characters: Annotated[
        int | None, Form(ge=1, le=MAX_EXTRACTED_TEXT_LENGTH)
    ] = None,
) -> DocumentResult:
    """Extract text from a document through Document Engine."""
    filename = Path(file.filename or "document").name

    try:
        # Reserve admission before copying multipart data into application memory.
        async with queue.slot():
            data = await read_upload_limited(file, MAX_DOCUMENT_SIZE)
            logger.info(
                "Document received: filename=%s, size=%s",
                log_safe(filename),
                len(data),
            )

            result = await process_document(
                data,
                filename,
                max_characters,
                queue=queue,
                _slot_acquired=True,
            )
            logger.info(
                "Document processed: filename=%s, format=%s, characters=%s",
                log_safe(filename),
                result["format"],
                result["characters"],
            )
            return result

    except HTTPException:
        raise
    except BackendError as error:
        logger.warning(
            "Document rejected: filename=%s, status=%s",
            log_safe(filename),
            error.status_code,
        )
        raise
    except Exception as error:
        logger.exception(
            "Document processing failed: filename=%s",
            log_safe(filename),
        )
        raise HTTPException(
            status_code=500,
            detail="Document processing failed",
        ) from error
    finally:
        await file.close()
