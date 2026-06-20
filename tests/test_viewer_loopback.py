#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0
"""End-to-end check of the REAL viewer flowgraph with a synthetic SDR.

Stands in an FM-modulated PAL/NTSC composite signal where build_source would
return the radio, so the actual viewer chain runs: FM quad-demod -> LPF ->
decoder -> converter -> sync_delay -> frame, plus the lock probe. Proves the
wiring assembles and runs, the FM demod recovers the picture, the roll applies
live, and the lock meter reads a real signal -- without any hardware."""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_pal_decode import STD, gen_field

SR = 20e6


def _make_iq(name):
    """Composite video FM-modulated to complex IQ at unity demod gain, so the
    viewer's own quadrature_demod recovers the exact composite levels."""
    from gnuradio import gr, blocks, analog
    import fpv_viewer as V
    std = STD[name]
    need = int(6.0 * std['w'] * std['h'] * (SR / (std['w'] * std['h'] * std['fr'])))
    sig = gen_field(std, SR, need)
    k = 1.0 / V.quad_demod_gain(SR)            # invert quad_demod_gain -> unity recovery
    tb = gr.top_block()
    src = blocks.vector_source_f(sig, False)
    fm = analog.frequency_modulator_fc(k)
    snk = blocks.vector_sink_c()
    tb.connect(src, fm, snk)
    tb.run()
    return list(snk.data())


def _run(name, iq):
    from gnuradio import blocks
    import fpv_viewer as V

    orig = V.build_source
    src_block = blocks.vector_source_c(iq, True)   # repeat: keep feeding frames
    V.build_source = lambda *a, **k: (src_block, lambda f: None)
    frame_out = '/tmp/fpv_loopback_%s.png' % name
    try:
        tb = V.viewer('uhd', SR, 5800e6, 30, '', None,
                      frame_out=frame_out, live=False, dcblock=False,
                      oversample=1, contrast=1.0, standard=name)
    finally:
        V.build_source = orig

    tb.start()
    time.sleep(2.0)
    lock = tb.lock_metric()
    tb.nudge_v(5)                                  # live roll while running
    rolled_off = tb.sync_off
    tb.nudge_h(-3)
    v, h = tb.sync_status()
    time.sleep(0.3)
    tb.stop()
    tb.wait()
    return lock, (v, h), rolled_off, frame_out


def _png_gradient_span(path):
    try:
        from PIL import Image
        import numpy as np
    except Exception:
        return None
    if not os.path.exists(path):
        return None
    a = np.asarray(Image.open(path).convert('L'), dtype=float)
    rm = a.mean(axis=1)
    return float(rm.max() - rm.min())


def run():
    print("== real viewer flowgraph, synthetic FM-modulated SDR (no hardware) ==")
    ok = True
    for name in ('ntsc', 'pal'):
        iq = _make_iq(name)
        lock, (v, h), rolled_off, frame_out = _run(name, iq)
        span = _png_gradient_span(frame_out)
        span_s = "n/a (no PIL)" if span is None else "%.0f" % span
        graph_ok = lock > 0.5 and (v, h) == (5, -3)
        pic_ok = span is None or span > 80
        good = graph_ok and pic_ok
        print("  [%s] graph ran: lock=%.2f  live-roll V/H=%s  frame=%s span=%s -> %s"
              % (name, lock, (v, h), os.path.basename(frame_out), span_s,
                 "PASS" if good else "FAIL"))
        ok &= good
    print()
    print("RESULT: %s" % ("PASS (real viewer assembles + runs; FM demod recovers the "
                          "picture; live roll + lock work)" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(run())
