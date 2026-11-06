#!/usr/bin/env python3
"""Encode one channel of raw 48 kHz stereo 16-bit audio as a track for decode.cq.

    encode.py IN.s16 CHANNEL START_S SECONDS CARDS [EXPECT]

CHANNEL is 0 for the left channel or 1 for the right. The track is written to CARDS, one card per line. If EXPECT
is given, the samples the decoder should output are written there, one per line. For each block of 64 samples, the
encoder picks the smallest step size M * 10^K (M from 1 to 9, K from 0 to 3) whose codes reach as far as the block
strays from the prediction (twice the previous sample, minus the one before it). It chooses each code against the
decoder's own prediction, and it never lets a sample go outside 16 bits.
"""
import struct, sys

N = 64
STEPS = [(k, m) for k in range(4) for m in range(1, 10)]

def block(xs, s1, s2, step):
    out = []
    for x in xs:
        e = 2 * s1 - s2
        lo, hi = max(-500, -((32768 + e) // step)), min(499, (32767 - e) // step)
        if lo > hi:
            return None   # this step can't keep a sample within 16 bits
        c = max(lo, min(hi, round((x - e) / step)))
        s = e + c * step
        out.append((c, s))
        s2, s1 = s1, s
    return out

def encode(xs):
    cards, samples, s1, s2 = [], [], 0, 0
    for b in range(0, len(xs), N):
        blk = xs[b:b + N]
        blk += [blk[-1]] * (N - len(blk))
        p = [s2, s1] + blk
        far = max(abs(p[i] - (2 * p[i - 1] - p[i - 2])) for i in range(2, len(p)))
        out, k, m = next((o, k, m) for k, m in STEPS if 499 * m * 10**k >= far
                         for o in [block(blk, s1, s2, m * 10**k)] if o)
        cards += [k, m] + [c for c, _ in out]
        samples += [s for _, s in out]
        s1, s2 = out[-1][1], out[-2][1]
    return cards + [-1], samples

def main():
    src, ch, start, secs, dst = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
    with open(src, "rb") as f:
        f.seek(int(start * 48000) * 4)
        raw = f.read(int(secs * 48000) * 4)
    xs = list(struct.unpack(f"<{len(raw) // 2}h", raw)[ch::2])
    cards, samples = encode(xs)
    with open(dst, "w") as f:
        f.write("\n".join(map(str, cards)) + "\n")
    if len(sys.argv) > 6:
        with open(sys.argv[6], "w") as f:
            f.write("\n".join(map(str, samples)) + "\n")

main()
