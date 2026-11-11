from dataclasses import dataclass
from pathlib import Path
import mimetypes


@dataclass
class FileInfo:
    path: Path
    name: str
    extension: str
    size_bytes: int
    mime_type: str | None



def inspect_file(file_path: str | Path) -> FileInfo:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")

    if not path.is_file():
        raise ValueError(f"Это папка, а не файл: {path}")

    mime, _ = mimetypes.guess_type(path.name)


    return FileInfo(
        path=path.resolve(),
        name=path.name,
        extension=path.suffix.lower(),
        size_bytes=path.stat().st_size,
        mime_type=mime
    )
