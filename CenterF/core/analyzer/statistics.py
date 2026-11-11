from dataclasses import dataclass
from core.analyzer.entropy import calc_shannon_entropy, calc_rle_ratio_estimate
from core.analyzer.file_detector import detect_block_type


@dataclass
class BlockStats:
    size: int
    entropy: float
    repeat_ratio: float
    unique_bytes: int
    block_type: str




def analyze_block(data: bytes) -> BlockStats:
    if not data:
        return BlockStats(0, 0.0, 0.0, 0, "empty")

    ent = calc_shannon_entropy(data)
    rep = calc_rle_ratio_estimate(data)
    uniq = len(set(data))
    b_type = detect_block_type(data)


    return BlockStats(
        size=len(data),
        entropy=ent,
        repeat_ratio=rep,
        unique_bytes=uniq,
        block_type=b_type
    )
