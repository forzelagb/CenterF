from dataclasses import dataclass
from pathlib import Path
import hashlib

DEFAULT_CHUNK_SIZE = 65536


@dataclass
class DataChunk:
    index: int
    data: bytes
    size: int
    sha256: str




def split_file_to_chunks(file_path: str | Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> list[DataChunk]:
    path = Path(file_path)
    chunks = []

    with open(path, "rb") as f:
        idx = 0
        while True:
            buf = f.read(chunk_size)
            if not buf:
                break

            checksum = hashlib.sha256(buf).hexdigest()
            chunks.append(DataChunk(
                index=idx,
                data=buf,
                size=len(buf),
                sha256=checksum
            ))
            idx += 1


    if not chunks:
        chunks.append(DataChunk(0, b"", 0, hashlib.sha256(b"").hexdigest()))

    return chunks
