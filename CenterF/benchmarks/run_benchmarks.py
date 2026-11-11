# Скрипт для проведения замеров (бенчмарков) для расчетно-экспериментального раздела курсовой работы.
# Сравнивает:
# 1. Обычное сжатие одним алгоритмом (только RLE, только Huffman, только ZLIB, BZIP2, LZMA)
# 2. Адаптивное поблочное сжатие CenterF (DataFlow) на неоднородном файле.

import hashlib
import time
import tempfile
from pathlib import Path

from core.compression.algorithms import (
    ALGO_RLE, ALGO_HUFFMAN, ALGO_ZLIB, ALGO_BZ2, ALGO_LZMA
)
from core.reconstruction.container import pack_file_to_container


def run_benchmark():
    print("=" * 78)
    print(" ЭКСПЕРИМЕНТАЛЬНОЕ ИССЛЕДОВАНИЕ ЭФФЕКТИВНОСТИ АДАПТИВНОГО СЖАТИЯ CENTERF")
    print("=" * 78)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        test_file = tmp_dir / "heterogeneous_dataset.bin"

        # Формируем реалистичный комбинированный файл (320 КБ, 5 блоков по 64 КБ)
        b_sz = 65536
        b0 = (b"\x00" * 1024 + b"A" * 512 + b"\xFF" * 512) * (b_sz // 2048)
        txt = b"2026-11-10 INFO [CenterF] Adaptive block processing telemetry record OK.\n"
        b1 = (txt * (b_sz // len(txt) + 1))[:b_sz]
        b2 = (b"EEEEEEEETTTTTTTTAAAAOOOOIIIINNNSHHRRDLU" * 2000)[:b_sz]
        b3 = b"".join(i.to_bytes(4, "little") + b"\x10\x20\x30\x40" for i in range(b_sz // 8))
        # блок 4: истинно высокоэнтропийный поток (имитация уже сжатого медиа-блока или крипто-контейнера)
        b4 = b"".join(hashlib.sha256(str(i).encode()).digest() for i in range(b_sz // 32))

        test_file.write_bytes(b0 + b1 + b2 + b3 + b4)
        orig_size = test_file.stat().st_size

        print(f"Тестовый комбинированный файл : {orig_size} байт (5 блоков по 64 КБ)")
        print("-" * 78)
        print(f"{'Режим работы':<34} | {'Итоговый размер':<16} | {'Сжатие (%)':<11} | {'Время (мс)'}")
        print("-" * 78)

        modes = [
            ("АДАПТИВНЫЙ CENTERF (DataFlow)", None),
            ("Только RLE (Самописный)", ALGO_RLE),
            ("Только Huffman (Самописный)", ALGO_HUFFMAN),
            ("Только ZLIB (Deflate)", ALGO_ZLIB),
            ("Только BZIP2 (BWT)", ALGO_BZ2),
            ("Только LZMA (7z)", ALGO_LZMA),
        ]

        for title, force_id in modes:
            out_dflow = tmp_dir / f"out_{force_id}.dflow"
            t0 = time.perf_counter()
            summary, blocks = pack_file_to_container(test_file, out_dflow, chunk_size=65536, force_algo=force_id)
            dt_ms = (time.perf_counter() - t0) * 1000.0

            print(
                f"{title:<34} | {summary.compressed_total_size:<10} байт | "
                f"{summary.compression_ratio_percent:>8.2f} %  | {dt_ms:>7.1f} мс"
            )

        print("-" * 78)


if __name__ == "__main__":
    run_benchmark()
