def rle_compress(data: bytes) -> bytes:
    if not data:
        return b""

    out = bytearray()
    n = len(data)
    i = 0

    while i < n:
        run_len = 1
        while i + run_len < n and data[i + run_len] == data[i] and run_len < 128:
            run_len += 1

        if run_len >= 3:
            out.append(run_len - 1)
            out.append(data[i])
            i += run_len
        else:
            lit_start = i
            lit_len = 0
            while i < n and lit_len < 128:
                if i + 2 < n and data[i] == data[i + 1] == data[i + 2]:
                    break
                i += 1
                lit_len += 1

            out.append(128 + lit_len - 1)
            out.extend(data[lit_start:lit_start + lit_len])


    return bytes(out)




def rle_decompress(data: bytes) -> bytes:
    if not data:
        return b""

    out = bytearray()
    n = len(data)
    i = 0

    while i < n:
        header = data[i]
        i += 1
        if header < 128:
            count = header + 1
            if i >= n:
                break
            val = data[i]
            i += 1
            out.extend([val] * count)
        else:
            count = header - 128 + 1
            out.extend(data[i:i + count])
            i += count


    return bytes(out)
