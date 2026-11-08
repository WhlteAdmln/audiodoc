# Copyright (c) 2026 Nikolai Zelensky
"""Document text extraction endpoint."""

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from backend.api.auth import require_key
from backend.api.schemas import DocumentResponse
from backend.common.limited_upload import read_upload_limited
from backend.common.safe_log import log_safe
from backend.config import settings
from backend.document_engine import document_queue, process_document
from backend.document_engine.limits import (
    MAX_DOCUMENT_SIZE,
    MAX_EXTRACTED_TEXT_LENGTH,
)
from backend.document_engine.result import DocumentResult
from backend.errors.base import BackendError

logger = logging.getLogger(__name__)

router = APIRouter(
    dependencies=[Depends(require_key(lambda: settings.DOCUMENT_API_KEY))]
)


@router.post("/process-document", response_model=DocumentResponse)
async def process_document_endpoint(
    file: Annotated[UploadFile, File()],
    max_characters: Annotated[
        int | None, Form(ge=1, le=MAX_EXTRACTED_TEXT_LENGTH)
    ] = None,
) -> DocumentResult:
    """Extract text from a document through Document Engine."""
    filename = Path(file.filename or "document").name

    try:
        # Reserve admission before copying multipart data into application memory.
        async with document_queue.slot():
            data = await read_upload_limited(file, MAX_DOCUMENT_SIZE)
            logger.info(
                "Document received: filename=%s, size=%s",
                log_safe(filename),
                len(data),
            )

            result = await process_document(
                data, filename, max_characters, _slot_acquired=True
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
