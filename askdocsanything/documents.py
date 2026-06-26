from __future__ import annotations

from pathlib import Path

from askdocsanything.models import DocumentInfo

SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".ppt": "powerpoint",
    ".pptx": "powerpoint",
    ".doc": "word",
    ".docx": "word",
    ".xls": "excel",
    ".xlsx": "excel",
    ".csv": "excel",
    ".tsv": "excel",
    ".pdf": "pdf",
    ".html": "html",
    ".htm": "html",
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".gif": "image",
    ".bmp": "image",
    ".tif": "image",
    ".tiff": "image",
}


def discover_documents(workdir: str | Path) -> list[DocumentInfo]:
    root = Path(workdir).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Document directory does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Document workdir must be a directory: {root}")

    documents: list[DocumentInfo] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        kind = SUPPORTED_EXTENSIONS.get(path.suffix.lower())
        if kind is None:
            continue
        documents.append(DocumentInfo.from_path(root, path, kind))
    return documents


def image_paths(workdir: str | Path, documents: list[DocumentInfo], max_images: int) -> list[Path]:
    root = Path(workdir).expanduser().resolve()
    paths: list[Path] = []
    for document in documents:
        if document.kind != "image":
            continue
        paths.append(root / document.path)
        if len(paths) >= max_images:
            break
    return paths
