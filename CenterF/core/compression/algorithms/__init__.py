import zlib
import bz2
import lzma
from core.compression.algorithms.rle_custom import rle_compress, rle_decompress
from core.compression.algorithms.huffman_custom import huffman_compress, huffman_decompress

ALGO_STORE   = 0
ALGO_RLE     = 1
ALGO_HUFFMAN = 2
ALGO_ZLIB    = 3
ALGO_BZ2     = 4
ALGO_LZMA    = 5

ALGO_NAMES = {
    ALGO_STORE:   "STORE (Без сжатия)",
    ALGO_RLE:     "RLE (Свой алгоритм)",
    ALGO_HUFFMAN: "Huffman (Свой алгоритм)",
    ALGO_ZLIB:    "ZLIB (Deflate)",
    ALGO_BZ2:     "BZIP2 (BWT)",
    ALGO_LZMA:    "LZMA (7z-движок)",
}




def compress_with_algo(data: bytes, algo_id: int) -> bytes:
    if not data or algo_id == ALGO_STORE:
        return data
    elif algo_id == ALGO_RLE:
        return rle_compress(data)
    elif algo_id == ALGO_HUFFMAN:
        return huffman_compress(data)
    elif algo_id == ALGO_ZLIB:
        return zlib.compress(data, level=6)
    elif algo_id == ALGO_BZ2:
        return bz2.compress(data, compresslevel=9)
    elif algo_id == ALGO_LZMA:
        return lzma.compress(data)
    else:
        raise ValueError(f"Неизвестный ID алгоритма: {algo_id}")




def decompress_with_algo(data: bytes, algo_id: int) -> bytes:
    if not data or algo_id == ALGO_STORE:
        return data
    elif algo_id == ALGO_RLE:
        return rle_decompress(data)
    elif algo_id == ALGO_HUFFMAN:
        return huffman_decompress(data)
    elif algo_id == ALGO_ZLIB:
        return zlib.decompress(data)
    elif algo_id == ALGO_BZ2:
        return bz2.decompress(data)
    elif algo_id == ALGO_LZMA:
        return lzma.decompress(data)
    else:
        raise ValueError(f"Неизвестный ID алгоритма при распаковке: {algo_id}")
