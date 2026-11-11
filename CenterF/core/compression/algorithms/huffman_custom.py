import heapq
from collections import Counter


class _Node:
    def __init__(self, freq: int, tie_id: int, byte_val: int | None = None, left=None, right=None):
        self.freq = freq
        self.tie_id = tie_id
        self.byte_val = byte_val
        self.left = left
        self.right = right

    def __lt__(self, other):
        if self.freq != other.freq:
            return self.freq < other.freq
        return self.tie_id < other.tie_id




def _build_tree_from_freqs(freqs: dict[int, int]) -> _Node:
    heap = [_Node(freq, b, byte_val=b) for b, freq in sorted(freqs.items())]
    heapq.heapify(heap)

    next_tie = 256
    while len(heap) > 1:
        left = heapq.heappop(heap)
        right = heapq.heappop(heap)
        merged = _Node(left.freq + right.freq, next_tie, left=left, right=right)
        next_tie += 1
        heapq.heappush(heap, merged)

    return heap[0]




def _build_codes(node, prefix="", code_map=None):
    if code_map is None:
        code_map = {}
    if node is None:
        return code_map

    if node.byte_val is not None:
        code_map[node.byte_val] = prefix if prefix else "0"
    else:
        _build_codes(node.left, prefix + "0", code_map)
        _build_codes(node.right, prefix + "1", code_map)
    return code_map




def huffman_compress(data: bytes) -> bytes:
    if not data:
        return b""

    freqs = dict(Counter(data))
    root = _build_tree_from_freqs(freqs)
    codes = _build_codes(root)

    bit_str = "".join(codes[b] for b in data)

    padding = (8 - len(bit_str) % 8) % 8
    bit_str += "0" * padding

    out = bytearray()
    out.extend(len(freqs).to_bytes(2, "big"))
    out.append(padding)

    for b, f in sorted(freqs.items()):
        out.append(b)
        out.extend(f.to_bytes(4, "big"))

    for i in range(0, len(bit_str), 8):
        byte_chunk = bit_str[i:i + 8]
        out.append(int(byte_chunk, 2))

    return bytes(out)




def huffman_decompress(data: bytes) -> bytes:
    if not data:
        return b""

    pos = 0
    num_symbols = int.from_bytes(data[pos:pos + 2], "big")
    pos += 2
    padding = data[pos]
    pos += 1

    freqs = {}
    for _ in range(num_symbols):
        b = data[pos]
        f = int.from_bytes(data[pos + 1:pos + 5], "big")
        freqs[b] = f
        pos += 5

    root = _build_tree_from_freqs(freqs)

    if root.byte_val is not None:
        total_len = sum(freqs.values())
        return bytes([root.byte_val] * total_len)

    bit_chunks = [f"{byte:08b}" for byte in data[pos:]]
    bit_str = "".join(bit_chunks)
    if padding > 0:
        bit_str = bit_str[:-padding]

    out = bytearray()
    curr = root
    for bit in bit_str:
        curr = curr.left if bit == "0" else curr.right
        if curr.byte_val is not None:
            out.append(curr.byte_val)
            curr = root

    return bytes(out)
