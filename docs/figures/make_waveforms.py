#!/usr/bin/env python3
"""Draw the waveform figures: the recording against what a CARDIAC decoded from its track.

    make_waveforms.py RECORDING.s16 DECODED.s16 START_S OUTDIR

RECORDING is one channel of the clip that was encoded, DECODED is what `lub` played from its track, both raw signed
16-bit samples at 48 kHz; START_S is where the clip starts in the piece. Writes waveform.svg (the whole clip, the
recording above the CARDIAC's output), waveform-loud.svg and waveform-soft.svg (ten milliseconds of the loudest and
of nearly the softest passage), and prints the error.
"""
import math
import struct
import sys

rec_path, dec_path, start_s, outdir = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
read = lambda p: (lambda b: list(struct.unpack(f"<{len(b) // 2}h", b)))(open(p, "rb").read())
a, d = read(rec_path), read(dec_path)
assert len(a) == len(d), "the recording and the decoded samples differ in length"
RATE, WIN = 48000, 480

err = [y - x for x, y in zip(a, d)]
snr = 10 * math.log10(sum(x * x for x in a) / sum(e * e for e in err))
rms = [math.sqrt(sum(x * x for x in a[i:i + WIN]) / WIN) for i in range(0, len(a) - WIN + 1, WIN)]
loud = max(range(len(rms)), key=rms.__getitem__) * WIN
soft = sorted(range(len(rms)), key=rms.__getitem__)[len(rms) // 50] * WIN   # near the quietest, not silence
same = sum(1 for e in err if e == 0)
print(f"{snr:.1f} dB; largest error {max(map(abs, err))}; {100 * same / len(a):.1f}% of samples exact; "
      f"loud at {start_s + loud / RATE:.2f} s, soft at {start_s + soft / RATE:.2f} s")

ink, faint, rc, dc, bg = "#1f2430", "#9aa3b5", "#2f6fb5", "#e0603a", "#ffffff"
font = 'font-family="Helvetica, Arial, sans-serif"'


def svg(W, H, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">\n'
            f'<rect width="{W}" height="{H}" fill="{bg}"/>\n' + "\n".join(body) + "\n</svg>\n")


def envelope(xs, x0, y0, w, h):
    """One channel squeezed into w columns: each column a line from its lowest sample to its highest."""
    Y = lambda v: y0 + h / 2 - v * (h / 2) / 32768
    cols = []
    for c in range(w):
        seg = xs[c * len(xs) // w:(c + 1) * len(xs) // w]
        cols.append(f"M{x0 + c + 0.5:.1f} {Y(max(seg)):.1f}V{Y(min(seg)):.1f}")
    return "".join(cols)


# the whole clip: two panels on the same scale
W, L, R, P = 900, 20, 20, 120
body = []
for n, (xs, colour, title) in enumerate(((a, rc, "The recording"), (d, dc, "Decoded by a CARDIAC"))):
    y0 = 34 + n * (P + 44)
    body.append(f'<text x="{L}" y="{y0 - 10}" {font} font-size="15" fill="{ink}">{title}</text>')
    body.append(f'<line x1="{L}" y1="{y0 + P / 2}" x2="{W - R}" y2="{y0 + P / 2}" stroke="{faint}" stroke-width="0.5"/>')
    body.append(f'<path d="{envelope(xs, L, y0, W - L - R, P)}" stroke="{colour}" stroke-width="1"/>')
end = start_s + len(a) / RATE
body.append(f'<text x="{L}" y="{34 + 2 * P + 44 + 18}" {font} font-size="13" fill="{faint}">{start_s:g} s</text>')
body.append(f'<text x="{W - R}" y="{34 + 2 * P + 44 + 18}" {font} font-size="13" fill="{faint}" text-anchor="end">'
            f'{end:g} s into the piece</text>')
open(f"{outdir}/waveform.svg", "w").write(svg(W, 34 + 2 * P + 44 + 26, body))


def zoom(first, name, title):
    """WIN samples: the recording as a line, each decoded sample as a dot."""
    W, H, L, R, T, B = 900, 300, 64, 20, 40, 44
    xs, ys = a[first:first + WIN], d[first:first + WIN]
    lo, hi = min(xs + ys), max(xs + ys)
    pad = (hi - lo) * 0.1 or 1
    lo, hi = lo - pad, hi + pad
    X = lambda i: L + i * (W - L - R) / (WIN - 1)
    Y = lambda v: T + (hi - v) * (H - T - B) / (hi - lo)
    body = [f'<text x="{L}" y="24" {font} font-size="15" fill="{ink}">{title}</text>']
    for v in (lo + pad, hi - pad):
        body.append(f'<text x="{L - 8}" y="{Y(v) + 4:.1f}" {font} font-size="12" fill="{faint}" text-anchor="end">'
                    f'{round(v)}</text>')
    body.append(f'<polyline points="{" ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(xs))}" fill="none" '
                f'stroke="{rc}" stroke-width="2.5"/>')
    body += [f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="1.8" fill="{dc}"/>' for i, v in enumerate(ys)]
    at = start_s + first / RATE
    body.append(f'<text x="{L}" y="{H - 14}" {font} font-size="13" fill="{faint}">{at:.3f} s</text>')
    body.append(f'<text x="{W - R}" y="{H - 14}" {font} font-size="13" fill="{faint}" text-anchor="end">'
                f'{at + WIN / RATE:.3f} s</text>')
    key = (f'<line x1="{W - 380}" y1="19" x2="{W - 356}" y2="19" stroke="{rc}" stroke-width="2.5"/>'
           f'<text x="{W - 350}" y="24" {font} font-size="13" fill="{ink}">the recording</text>'
           f'<circle cx="{W - 248}" cy="19" r="3" fill="{dc}"/>'
           f'<text x="{W - 240}" y="24" {font} font-size="13" fill="{ink}">a CARDIAC, one dot a sample</text>')
    body.append(key)
    open(f"{outdir}/{name}.svg", "w").write(svg(W, H, body))


zoom(loud, "waveform-loud", "Ten milliseconds of the loudest passage")
zoom(soft, "waveform-soft", "Ten milliseconds of one of the softest passages")
