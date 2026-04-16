from __future__ import annotations

import base64
from pathlib import Path

import fitz


def _to_data_url(raw: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(raw).decode('utf-8')
    return f'data:{mime_type};base64,{encoded}'


def prepare_multimodal_payload(file_path: str) -> tuple[list[str], str]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(file_path)

    suffix = path.suffix.lower()
    if suffix == '.pdf':
        return _pdf_to_images(path)
    mime_type = 'image/png' if suffix == '.png' else 'image/jpeg'
    raw = path.read_bytes()
    return [_to_data_url(raw, mime_type)], ''


def _pdf_to_images(path: Path) -> tuple[list[str], str]:
    raw = path.read_bytes()
    try:
        doc = fitz.open(stream=raw, filetype='pdf')
    except Exception:
        return [], ''

    image_urls: list[str] = []
    text_parts: list[str] = []
    for page_index in range(min(len(doc), 3)):
        page = doc[page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        image_urls.append(_to_data_url(pix.tobytes('png'), 'image/png'))
        text_parts.append(page.get_text().strip())
    return image_urls, '\n'.join(part for part in text_parts if part)
