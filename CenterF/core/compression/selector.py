from dataclasses import dataclass
from core.analyzer.statistics import BlockStats, analyze_block
from core.chunking.chunker import DataChunk
from core.compression.algorithms import (
    ALGO_STORE, ALGO_RLE, ALGO_HUFFMAN, ALGO_ZLIB, ALGO_BZ2, ALGO_LZMA,
    ALGO_NAMES, compress_with_algo
)


@dataclass
class ProcessedBlock:
    index: int
    algo_id: int
    algo_name: str
    raw_size: int
    compressed_size: int
    entropy: float
    block_type: str
    sha256: str
    payload: bytes
    reason: str




def select_candidates_for_block(stats: BlockStats) -> tuple[list[int], str]:
    if stats.size == 0:
        return [ALGO_STORE], "Пустой блок"

    if stats.entropy > 7.65 and stats.repeat_ratio < 0.05:
        return [ALGO_STORE, ALGO_ZLIB], "Высокая энтропия (>7.65) — данные почти несжимаемы"

    if stats.block_type == "sparse_zeros" or stats.repeat_ratio >= 0.35:
        return [ALGO_RLE, ALGO_HUFFMAN, ALGO_ZLIB, ALGO_BZ2], f"Много серий повторов ({int(stats.repeat_ratio*100)}%) — приоритет RLE/BWT"

    if stats.block_type == "text":
        return [ALGO_HUFFMAN, ALGO_ZLIB, ALGO_BZ2, ALGO_LZMA], "Текстовая структура — тест Хаффмана, BWT и словарных алгоритмов"

    if stats.entropy < 5.5:
        return [ALGO_RLE, ALGO_HUFFMAN, ALGO_ZLIB, ALGO_LZMA], "Структурированный бинарный блок (низкая энтропия)"

    return [ALGO_ZLIB, ALGO_LZMA, ALGO_BZ2], "Сложный бинарный блок — поиск дальних совпадений (LZMA/ZLIB)"




def process_chunk_adaptively(chunk: DataChunk, force_algo: int | None = None) -> ProcessedBlock:
    stats = analyze_block(chunk.data)

    if force_algo is not None:
        comp_data = compress_with_algo(chunk.data, force_algo)
        return ProcessedBlock(
            index=chunk.index,
            algo_id=force_algo,
            algo_name=ALGO_NAMES[force_algo],
            raw_size=chunk.size,
            compressed_size=len(comp_data),
            entropy=stats.entropy,
            block_type=stats.block_type,
            sha256=chunk.sha256,
            payload=comp_data,
            reason="Выбран вручную пользователем"
        )

    candidates, reason = select_candidates_for_block(stats)

    best_algo = ALGO_STORE
    best_data = chunk.data

    for algo_id in candidates:
        if algo_id == ALGO_STORE:
            continue
        try:
            attempt = compress_with_algo(chunk.data, algo_id)
            if len(attempt) < len(best_data):
                best_data = attempt
                best_algo = algo_id
        except Exception:
            continue

    return ProcessedBlock(
        index=chunk.index,
        algo_id=best_algo,
        algo_name=ALGO_NAMES[best_algo],
        raw_size=chunk.size,
        compressed_size=len(best_data),
        entropy=stats.entropy,
        block_type=stats.block_type,
        sha256=chunk.sha256,
        payload=best_data,
        reason=reason
    )
