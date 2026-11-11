import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from core.analyzer.file_info import inspect_file
from core.chunking.chunker import split_file_to_chunks, DEFAULT_CHUNK_SIZE
from core.compression.selector import ProcessedBlock, process_chunk_adaptively
from core.compression.algorithms import decompress_with_algo

MAGIC_BYTES = b"CENF"
FORMAT_VERSION = 1


@dataclass
class ContainerSummary:
    container_path: Path
    original_name: str
    original_size: int
    compressed_total_size: int
    total_blocks: int
    file_sha256: str
    blocks_meta: list[dict]

    @property
    def compression_ratio_percent(self) -> float:
        if self.original_size == 0:
            return 0.0
        saved = self.original_size - self.compressed_total_size
        return round((saved / self.original_size) * 100, 2)




def pack_file_to_container(
    input_path: str | Path,
    output_path: str | Path | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    force_algo: int | None = None,
    progress_callback=None
) -> tuple[ContainerSummary, list[ProcessedBlock]]:
    in_path = Path(input_path)
    info = inspect_file(in_path)

    if output_path is None:
        out_path = in_path.with_suffix(in_path.suffix + ".cenf")
    else:
        out_path = Path(output_path)

    full_hasher = hashlib.sha256()
    with open(in_path, "rb") as f:
        while chunk_bytes := f.read(131072):
            full_hasher.update(chunk_bytes)
    file_sha256 = full_hasher.hexdigest()

    chunks = split_file_to_chunks(in_path, chunk_size=chunk_size)
    processed_blocks: list[ProcessedBlock] = []
    blocks_meta = []

    current_offset = 0
    total = len(chunks)

    for idx, ch in enumerate(chunks):
        pb = process_chunk_adaptively(ch, force_algo=force_algo)
        processed_blocks.append(pb)

        blocks_meta.append({
            "index": pb.index,
            "algo_id": pb.algo_id,
            "algo_name": pb.algo_name,
            "raw_size": pb.raw_size,
            "compressed_size": pb.compressed_size,
            "offset": current_offset,
            "entropy": pb.entropy,
            "block_type": pb.block_type,
            "sha256": pb.sha256,
            "reason": pb.reason
        })
        current_offset += pb.compressed_size

        if progress_callback:
            progress_callback(idx + 1, total, pb)

    manifest = {
        "format": "CenterF Container",
        "version": FORMAT_VERSION,
        "original_name": info.name,
        "original_size": info.size_bytes,
        "chunk_size": chunk_size,
        "total_blocks": len(processed_blocks),
        "file_sha256": file_sha256,
        "blocks": blocks_meta
    }

    header_bytes = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
    header_len = len(header_bytes)

    with open(out_path, "wb") as out_f:
        out_f.write(MAGIC_BYTES)
        out_f.write(bytes([FORMAT_VERSION]))
        out_f.write(header_len.to_bytes(4, "big"))
        out_f.write(header_bytes)
        for pb in processed_blocks:
            out_f.write(pb.payload)

    total_container_size = out_path.stat().st_size

    summary = ContainerSummary(
        container_path=out_path,
        original_name=info.name,
        original_size=info.size_bytes,
        compressed_total_size=total_container_size,
        total_blocks=len(processed_blocks),
        file_sha256=file_sha256,
        blocks_meta=blocks_meta
    )
    return summary, processed_blocks




def read_container_manifest(container_path: str | Path) -> tuple[dict, int]:
    path = Path(container_path)
    with open(path, "rb") as f:
        magic = f.read(4)
        if magic != MAGIC_BYTES:
            raise ValueError("Файл не является контейнером CenterF (.cenf)!")
        version = f.read(1)[0]
        if version != FORMAT_VERSION:
            raise ValueError(f"Неподдерживаемая версия контейнера: {version}")
        header_len = int.from_bytes(f.read(4), "big")
        header_json = f.read(header_len).decode("utf-8")
        manifest = json.loads(header_json)
        data_start_offset = 4 + 1 + 4 + header_len
        return manifest, data_start_offset




def read_single_compressed_block(container_path: str | Path, block_index: int) -> tuple[dict, bytes]:
    manifest, data_start = read_container_manifest(container_path)
    blocks = manifest["blocks"]
    if block_index < 0 or block_index >= len(blocks):
        raise IndexError(f"Блок #{block_index} не существует в контейнере")

    b_meta = blocks[block_index]
    offset = data_start + b_meta["offset"]
    comp_size = b_meta["compressed_size"]

    with open(container_path, "rb") as f:
        f.seek(offset)
        payload = f.read(comp_size)

    return b_meta, payload




def unpack_container(
    container_path: str | Path,
    output_dir: str | Path | None = None,
    progress_callback=None
) -> Path:
    c_path = Path(container_path)
    manifest, data_start = read_container_manifest(c_path)

    orig_name = manifest["original_name"]
    if output_dir is None:
        out_file = c_path.parent / ("restored_" + orig_name)
    else:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / orig_name

    blocks = manifest["blocks"]
    total = len(blocks)
    full_hasher = hashlib.sha256()

    with open(c_path, "rb") as in_f, open(out_file, "wb") as out_f:
        in_f.seek(data_start)
        for idx, b_meta in enumerate(blocks):
            comp_size = b_meta["compressed_size"]
            algo_id = b_meta["algo_id"]
            expected_sha = b_meta["sha256"]

            comp_data = in_f.read(comp_size)
            raw_data = decompress_with_algo(comp_data, algo_id)

            actual_sha = hashlib.sha256(raw_data).hexdigest()
            if actual_sha != expected_sha:
                raise ValueError(
                    f"Ошибка контрольной суммы в блоке #{idx}! "
                    f"Ожидался {expected_sha[:8]}..., получен {actual_sha[:8]}..."
                )

            out_f.write(raw_data)
            full_hasher.update(raw_data)

            if progress_callback:
                progress_callback(idx + 1, total, b_meta)

    if full_hasher.hexdigest() != manifest["file_sha256"]:
        raise ValueError("Итоговая контрольная сумма файла не совпала с манифестом!")

    return out_file
