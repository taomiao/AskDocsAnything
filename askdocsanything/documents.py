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


def resolve_document_root(path: str | Path) -> Path:
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(f"Document path does not exist: {target}")
    if target.is_file():
        return target.parent
    if target.is_dir():
        return target
    raise ValueError(f"Document path must be a file or directory: {target}")


def discover_documents(workdir: str | Path) -> list[DocumentInfo]:
    target = Path(workdir).expanduser().resolve()
    root = resolve_document_root(target)
    documents: list[DocumentInfo] = []
    if target.is_file():
        kind = SUPPORTED_EXTENSIONS.get(target.suffix.lower())
        if kind is None:
            return []
        return [DocumentInfo.from_path(root, target, kind)]

    for path in sorted(target.rglob("*")):
        if not path.is_file():
            continue
        kind = SUPPORTED_EXTENSIONS.get(path.suffix.lower())
        if kind is None:
            continue
        documents.append(DocumentInfo.from_path(root, path, kind))
    return documents


def image_paths(workdir: str | Path, documents: list[DocumentInfo], max_images: int) -> list[Path]:
    root = resolve_document_root(workdir)
    paths: list[Path] = []
    for document in documents:
        if document.kind != "image":
            continue
        paths.append(root / document.path)
        if len(paths) >= max_images:
            break
    return paths
