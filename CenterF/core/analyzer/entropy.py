import math
from collections import Counter


def calc_shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0

    length = len(data)
    counts = Counter(data)

    entropy = 0.0
    for count in counts.values():
        p = count / length
        entropy -= p * math.log2(p)

    return round(entropy, 4)




def calc_rle_ratio_estimate(data: bytes) -> float:
    if len(data) < 2:
        return 0.0

    repeats = 0
    for i in range(1, len(data)):
        if data[i] == data[i - 1]:
            repeats += 1

    return round(repeats / len(data), 4)
