"""Document loading and preview helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from docx import Document
from nltk.tokenize import sent_tokenize
from PIL import Image
from pypdf import PdfReader

from semantic_bridge.constants import SAMPLE_TRANSCRIPTS
from semantic_bridge.types import DocumentMap, DocumentPreview

try:
    import pytesseract
except ImportError:  # pragma: no cover - optional dependency at runtime
    pytesseract = None


SUPPORTED_DOCUMENT_SUFFIXES = {
    ".txt",
    ".json",
    ".docx",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
}


def ensure_data_directory(data_dir: Path) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def write_sample_documents(data_dir: Path, sample_transcripts: DocumentMap | None = None) -> DocumentMap:
    documents = sample_transcripts or SAMPLE_TRANSCRIPTS
    ensure_data_directory(data_dir)
    for filename, content in documents.items():
        (data_dir / filename).write_text(content.strip())
    return documents


def load_text_document(filepath: Path) -> str:
    return filepath.read_text()


def load_json_document(filepath: Path) -> str:
    payload = json.loads(filepath.read_text())
    if isinstance(payload, dict):
        for key in ("text", "content", "body", "description"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return json.dumps(payload, indent=2)


def load_docx_document(filepath: Path) -> str:
    document = Document(filepath)
    return "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())


def load_pdf_document(filepath: Path) -> str:
    reader = PdfReader(str(filepath))
    page_text = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            page_text.append(text)
    return "\n".join(page_text)


def load_image_document(filepath: Path) -> str:
    if pytesseract is None:
        raise RuntimeError("pytesseract is not available for OCR image extraction")
    image = Image.open(filepath)
    return pytesseract.image_to_string(image)


def load_document(filepath: Path) -> str:
    suffix = filepath.suffix.lower()
    if suffix == ".txt":
        return load_text_document(filepath)
    if suffix == ".json":
        return load_json_document(filepath)
    if suffix == ".docx":
        return load_docx_document(filepath)
    if suffix == ".pdf":
        return load_pdf_document(filepath)
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        return load_image_document(filepath)
    raise ValueError(f"Unsupported document type: {filepath.suffix}")


def _is_hidden_path(filepath: Path) -> bool:
    return any(part.startswith(".") for part in filepath.parts)


def _document_roots(data_dir: Path) -> list[Path]:
    preferred_roots = [data_dir / "cleaned", data_dir / "raw"]
    available_roots = [root for root in preferred_roots if root.exists() and root.is_dir()]
    return available_roots or [data_dir]


def load_documents(data_dir: Path) -> DocumentMap:
    documents: DocumentMap = {}
    for root in _document_roots(data_dir):
        for filepath in sorted(root.rglob("*")):
            if _is_hidden_path(filepath.relative_to(root)):
                continue
            if not filepath.is_file() or filepath.suffix.lower() not in SUPPORTED_DOCUMENT_SUFFIXES:
                continue
            if filepath.name in documents:
                continue
            try:
                documents[filepath.name] = load_document(filepath)
            except Exception as exc:
                print(f"Skipping {filepath.name}: {exc}")
    return documents


def preview_documents(documents: DocumentMap, preview_chars: int = 200) -> list[DocumentPreview]:
    previews = []
    for filename, content in documents.items():
        preview = content[:preview_chars] + "..." if len(content) > preview_chars else content
        previews.append({"filename": filename, "preview": preview})
    return previews


def build_stats_table(documents: DocumentMap) -> pd.DataFrame:
    stats = []
    for filename, content in documents.items():
        stats.append(
            {
                "File": filename,
                "Characters": len(content),
                "Words": len(content.split()),
                "Sentences": len(sent_tokenize(content)),
            }
        )
    return pd.DataFrame(stats)

