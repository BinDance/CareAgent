from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from eldercare_api.config import get_settings


def _fallback_upload_dir() -> Path:
    path = Path(tempfile.gettempdir()) / 'eldercare-uploads'
    path.mkdir(parents=True, exist_ok=True)
    return path


def clear_uploads() -> int:
    cleared = 0
    settings = get_settings()
    for directory in {settings.resolved_upload_dir, _fallback_upload_dir()}:
        if not directory.exists():
            continue
        for item in directory.iterdir():
            if item.is_file():
                item.unlink(missing_ok=True)
                cleared += 1
    return cleared


async def save_upload(upload: UploadFile) -> Path:
    settings = get_settings()
    preferred_dir = settings.resolved_upload_dir
    suffix = Path(upload.filename or '').suffix or '.bin'
    content = await upload.read()

    try:
        preferred_dir.mkdir(parents=True, exist_ok=True)
        target = preferred_dir / f'{uuid4()}{suffix}'
        target.write_bytes(content)
        return target
    except PermissionError:
        fallback_dir = _fallback_upload_dir()
        target = fallback_dir / f'{uuid4()}{suffix}'
        target.write_bytes(content)
        return target
