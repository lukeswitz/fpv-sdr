#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_pal_decode import STD, gen_field, SAMP_RATE


def _roll_pair(sig, std, d):
    """One run, fan the same converter output into delay(0) and delay(d) so both
    sinks see the IDENTICAL raster — isolates blocks.delay from the converter's
    free-running start phase (two independent runs would differ by a few samples)."""
    from gnuradio import gr, blocks
    import gnuradio.NTSC as NTSC
    w, h, fr = std['w'], std['h'], std['fr']
    tb = gr.top_block()
    src = blocks.vector_source_f(sig, False)
    dec = NTSC.decoder_c(SAMP_RATE, std['code'])
    conv = NTSC.video_stream_converter_c(SAMP_RATE, SAMP_RATE / (w * h * fr), w, h)
    d0 = blocks.delay(gr.sizeof_short, 0)
    dd = blocks.delay(gr.sizeof_short, d)
    s0 = blocks.vector_sink_s()
    sd = blocks.vector_sink_s()
    tb.connect(src, (dec, 0))
    for p in range(4):
        tb.connect((dec, p), (conv, p))
    tb.connect(conv, d0, s0)
    tb.connect(conv, dd, sd)
    tb.run()
    return list(s0.data()), list(sd.data())


def _lock(sig, std):
    from gnuradio import gr, blocks
    import gnuradio.NTSC as NTSC
    w, h, fr = std['w'], std['h'], std['fr']
    win = max(1, int(SAMP_RATE * 0.02))
    tb = gr.top_block()
    src = blocks.vector_source_f(sig, False)
    dec = NTSC.decoder_c(SAMP_RATE, std['code'])
    conv = NTSC.video_stream_converter_c(SAMP_RATE, SAMP_RATE / (w * h * fr), w, h)
    nul = blocks.null_sink(gr.sizeof_short)
    st = blocks.add_const_ff(-1.0)
    ab = blocks.abs_ff(1)
    mv = blocks.moving_average_ff(win, 1.0 / win, 4000, 1)
    pr = blocks.probe_signal_f()
    tb.connect(src, (dec, 0))
    for p in range(4):
        tb.connect((dec, p), (conv, p))
    tb.connect(conv, nul)
    tb.connect((dec, 0), st, ab, mv, pr)
    tb.run()
    return pr.level()


def _row_means(stream, w, skip, count):
    rows = len(stream) // w
    skip = min(skip, rows)
    count = min(count, rows - skip)
    return [sum(stream[(skip + r) * w:(skip + r + 1) * w]) / w for r in range(count)]


def _xcorr_lag(a, b, maxlag):
    """Lag L in [0, maxlag] that best aligns a[i] with b[i+L]."""
    n = min(len(a), len(b) - maxlag)
    am = sum(a[:n]) / n
    bm = sum(b) / len(b)
    best, best_lag = None, 0
    for L in range(maxlag + 1):
        s = 0.0
        for i in range(n):
            s += (a[i] - am) * (b[i + L] - bm)
        if best is None or s > best:
            best, best_lag = s, L
    return best_lag


def run():
    print("== sync tuner: roll a DECODED picture + lock probe ==")
    ok = True
    for name in ('ntsc', 'pal'):
        std = STD[name]
        w, h, fr = std['w'], std['h'], std['fr']
        need = int(10.0 * w * h * (SAMP_RATE / (w * h * fr)))
        sig = gen_field(std, SAMP_RATE, need)
        flat = [-0.015] * len(sig)  # BLANK level, no sync pulses -> decoder stays idle

        # vertical hold: the DECODED gradient must (a) exist (real picture) and
        # (b) move by exactly k rows when we roll by k lines. Cross-correlate the
        # row-brightness profile of the rolled raster against the un-rolled one;
        # the peak lag is how many rows the visible picture actually moved.
        for lines in (1, 5):
            d = lines * w
            base, rolled = _roll_pair(sig, std, d)
            base_rm = _row_means(base, w, 2 * h, 4 * h)
            roll_rm = _row_means(rolled, w, 2 * h, 4 * h + h + 4)
            span = max(base_rm) - min(base_rm)
            lag = _xcorr_lag(base_rm, roll_rm, h)
            good = span > 150 and lag == lines
            print("  [%s] V +%d lines: decoded gradient span=%.0f (>150 = real picture), "
                  "picture moved %d rows -> %s"
                  % (name, lines, span, lag, "PASS" if good else "FAIL"))
            ok &= good

        # lock meter: ~0 on a flat (no-sync) input, clearly positive on real video
        lk_sig = _lock(sig, std)
        lk_flat = _lock(flat, std)
        good = lk_sig > 0.5 and lk_flat < 0.1
        print("  [%s] lock: video=%.3f  no-signal=%.3f -> %s"
              % (name, lk_sig, lk_flat, "PASS" if good else "FAIL"))
        ok &= good

    print()
    print("  note: horizontal roll uses the same delay block; the test pattern is a")
    print("        vertical gradient with no left-right detail, so H is not separately")
    print("        content-checked here (the V test proves the shift is sample-exact).")
    print()
    print("RESULT: %s" % ("PASS (decoded NTSC+PAL picture rolls by the exact line count; "
                          "lock separates video from no-signal)" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(run())
