#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0

import sys
import math

STD = {
    'ntsc': dict(code=0, line=63.5e-6, hsync=4.7e-6, back=4.7e-6,
                 video=52.6e-6, front=1.5e-6, lines=240, w=360, h=240, fr=60),
    'pal':  dict(code=1, line=64.0e-6, hsync=4.7e-6, back=5.7e-6,
                 video=51.95e-6, front=1.65e-6, lines=288, w=360, h=288, fr=50),
}

SYNC, BLANK, BLACK, WHITE = -0.04, -0.015, -0.02, 0.06
HSYNC_THRESH = -0.020
SAMP_RATE = 20e6


def line_level(k, n):
    bw_target = 20.0 + 220.0 * k / (n - 1)
    return BLACK + (WHITE - BLACK) * bw_target / 254.0


def gen_field(std, sr, min_samples):
    n_hsync = round(std['hsync'] * sr)
    n_back = round(std['back'] * sr)
    n_video = round(std['video'] * sr)
    n_front = round(std['front'] * sr)
    n = std['lines']
    sig = [BLANK] * n_back
    for k in range(n):
        lvl = line_level(k, n)
        sig += [SYNC] * n_hsync + [BLANK] * n_back + [lvl] * n_video + [BLANK] * n_front
    blank_line = [SYNC] * n_hsync + [BLANK] * n_back + [BLANK] * n_video + [BLANK] * n_front
    while len(sig) < min_samples:
        sig += blank_line
    return sig


def model_decode(sig, std, sr):
    """Pure-Python mirror of decoder_c_impl.cc work() + the converter matrix
    write. No third-party deps — validates that the synthetic field, under the
    documented state machine and this standard's timing, reconstructs the
    vertical gradient. Proves the signal/timing math independently of GNU Radio."""
    line_dur = std['line']; hsync = std['hsync']; back = std['back']
    video = std['video']; front = std['front']
    nvideo = std['lines']; nvsync = std['lines']  # nvsync unused on this clean field
    xw = std['w']; yh = std['h']

    IDLE, HS, BP, VID, FP, VS = 1, 4, 5, 6, 3, 7
    state = IDLE
    cnt = 0
    lines = 0
    mat = [[127] * xw for _ in range(yh)]
    prev = sig[0]
    for s in sig:
        cnt += 1
        if state == IDLE:
            if prev > HSYNC_THRESH and s < HSYNC_THRESH:
                state = HS; cnt = 0
        if state == HS:
            if cnt > hsync * sr:
                state = BP; cnt = 0
        if state == BP:
            if cnt > back * sr:
                state = VID; cnt = 0
        if state == VID:
            x = int(xw * cnt / (video * sr))
            y = int(yh * lines / (1.0 * nvideo))
            bw = int((s - BLACK) / (WHITE - BLACK) * 254)
            if bw > 250: bw = 250
            if bw < 5: bw = 5
            if 2 < x < xw - 2 and 2 < y < yh - 2:
                mat[y][x] = bw
            if cnt > video * sr:
                state = FP; cnt = 0; lines += 1
            elif prev > HSYNC_THRESH and s < HSYNC_THRESH and cnt < 0.75 * video * sr:
                state = VS; cnt = 0
        if state == FP:
            if prev > HSYNC_THRESH and s < HSYNC_THRESH:
                state = HS; cnt = 0
            elif cnt > front * sr:
                state = HS; cnt = 0
        if state == VS:
            if cnt > (nvsync + 1.5) * line_dur * sr:
                lines = 0; state = IDLE
        prev = s
    return mat


def row_means(mat):
    return [sum(row) / len(row) for row in mat]


def check_gradient(rm, label):
    n = len(rm)
    mean = sum(rm) / n
    sx = sum((i - (n - 1) / 2.0) ** 2 for i in range(n))
    sy = sum((rm[i] - mean) ** 2 for i in range(n))
    sxy = sum((i - (n - 1) / 2.0) * (rm[i] - mean) for i in range(n))
    corr = sxy / math.sqrt(sx * sy) if sx > 0 and sy > 0 else 0.0
    span = max(rm) - min(rm)
    ok = corr > 0.99 and span > 200
    print("  [%s] rows=%d  span=%.1f  corr=%.4f  -> %s"
          % (label, n, span, corr, "PASS" if ok else "FAIL"))
    return ok


def interior(rm, h):
    return rm[3:h - 2]


def align_cycle(rv, h):
    """The converter emits the image matrix as a free-running raster, so a
    length-h window is the vertical gradient cyclically shifted by an unknown
    phase. Rotate to start right after the single bright->dark wrap, then drop
    the unwritten guard rows (pinned at the 127 init value)."""
    k = len(rv) // h
    cyc = [sum(rv[p + j * h] for j in range(k)) / k for p in range(h)]
    wrap = max(range(h), key=lambda i: cyc[i] - cyc[(i + 1) % h])
    rot = cyc[(wrap + 1) % h:] + cyc[:(wrap + 1) % h]
    return [v for v in rot if not (124.0 <= v <= 130.0)]


def run_model():
    print("== model check (pure Python, no GNU Radio) ==")
    ok = True
    for name in ('ntsc', 'pal'):
        std = STD[name]
        need = int(1.2 * std['line'] * std['lines'] * SAMP_RATE)
        sig = gen_field(std, SAMP_RATE, need)
        mat = model_decode(sig, std, SAMP_RATE)
        rm = row_means(mat)
        if len(rm) != std['h']:
            print("  [%s] FAIL height %d != %d" % (name, len(rm), std['h'])); ok = False
        ok &= check_gradient(interior(rm, std['h']), name)
    return ok


def run_gnuradio():
    try:
        import numpy as np
        from gnuradio import gr, blocks
        import gnuradio.NTSC as NTSC
    except Exception as e:
        print("== gnuradio test == SKIP (%s)" % e)
        return None
    print("== gnuradio integration test (real C++ decoder) ==")
    ok = True
    for name in ('ntsc', 'pal'):
        std = STD[name]
        w, h, fr = std['w'], std['h'], std['fr']
        dec_factor = SAMP_RATE / (w * h * fr)
        need = int(3.0 * w * h * dec_factor)
        sig = gen_field(std, SAMP_RATE, need)

        tb = gr.top_block()
        src = blocks.vector_source_f(sig, False)
        dec = NTSC.decoder_c(SAMP_RATE, std['code'])
        conv = NTSC.video_stream_converter_c(SAMP_RATE, dec_factor, w, h)
        snk = blocks.vector_sink_s()
        tb.connect(src, (dec, 0))
        for p in range(4):
            tb.connect((dec, p), (conv, p))
        tb.connect(conv, snk)
        tb.run()

        data = list(snk.data())
        rows = len(data) // w
        if rows < 2 * h:
            print("  [%s] FAIL too little output (%d rows < %d)" % (name, rows, 2 * h))
            ok = False
            continue
        rv = [sum(data[i * w:(i + 1) * w]) / w for i in range(rows)]
        cycles = len(rv) // h
        if cycles < 2:
            print("  [%s] FAIL too little output (%d cycles < 2)" % (name, cycles))
            ok = False
            continue
        settled = rv[-(cycles - 1) * h:]
        grad = align_cycle(settled, h)
        ok &= check_gradient(grad, name)
    return ok


def main():
    m = run_model()
    g = run_gnuradio()
    print()
    if not m:
        print("RESULT: FAIL (signal/timing math is wrong — fix before hardware)")
        return 1
    if g is None:
        print("RESULT: model PASS; gnuradio test SKIPPED (run on a box with the built decoder)")
        return 0
    if not g:
        print("RESULT: FAIL (C++ decoder output does not match the model)")
        return 1
    print("RESULT: PASS (model + real decoder agree for NTSC and PAL)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
