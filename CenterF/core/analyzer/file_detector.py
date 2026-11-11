def detect_block_type(data: bytes) -> str:
    if not data:
        return "empty"

    zero_count = data.count(0)
    if zero_count / len(data) > 0.7:
        return "sparse_zeros"


    printable = 0
    sample = data[:4096]
    for b in sample:
        if (32 <= b <= 126) or b in (9, 10, 13) or (b >= 128):
            printable += 1


    if 0 not in sample and (printable / len(sample)) > 0.85:
        return "text"

    return "binary"
