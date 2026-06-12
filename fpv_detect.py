#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0

import os
import sys
import time
import math
import signal
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gnuradio import gr, blocks, analog, filter
from gnuradio.filter import firdes
from gnuradio.fft import window

try:
    import gnuradio.NTSC as NTSC
    HAVE_NTSC = True
except Exception:
    NTSC = None
    HAVE_NTSC = False

from fpv_sdr import build_source, quad_demod_gain


class detector(gr.top_block):
    def __init__(self, sdr, samp_rate, gain, start_freq, dev_args, antenna):
        gr.top_block.__init__(self, "FPV Detector", catch_exceptions=True)
        self.samp_rate = samp_rate

        self.src, self._retune = build_source(
            samp_rate, start_freq, gain, sdr=sdr, dev_args=dev_args, antenna=antenna)

        pwr_win = max(1, int(samp_rate * 0.005))
        lock_win = max(1, int(samp_rate * 0.02))

        self.have_lock = HAVE_NTSC

        self.dcblock = filter.dc_blocker_cc(32, True)
        self.connect(self.src, self.dcblock)

        self.mag2 = blocks.complex_to_mag_squared(1)
        self.pwr_avg = blocks.moving_average_ff(pwr_win, 1.0 / pwr_win, 4000, 1)
        self.pwr_probe = blocks.probe_signal_f()
        self.connect(self.dcblock, self.mag2, self.pwr_avg, self.pwr_probe)

        if self.have_lock:
            self.qdemod = analog.quadrature_demod_cf(quad_demod_gain(samp_rate))
            self.lpf = filter.fir_filter_fff(
                1, firdes.low_pass(1, samp_rate, 2e6, 2e6, window.WIN_HAMMING, 6.76))
            self.dec = NTSC.decoder_c(samp_rate)
            self.state_shift = blocks.add_const_ff(-1.0)
            self.state_abs = blocks.abs_ff(1)
            self.lock_avg = blocks.moving_average_ff(lock_win, 1.0 / lock_win, 4000, 1)
            self.lock_probe = blocks.probe_signal_f()
            self.null1 = blocks.null_sink(gr.sizeof_float)
            self.null2 = blocks.null_sink(gr.sizeof_float)
            self.null3 = blocks.null_sink(gr.sizeof_float)

            self.connect(self.dcblock, self.qdemod, self.lpf, (self.dec, 0))
            self.connect((self.dec, 0), self.state_shift,
                         self.state_abs, self.lock_avg, self.lock_probe)
            self.connect((self.dec, 1), self.null1)
            self.connect((self.dec, 2), self.null2)
            self.connect((self.dec, 3), self.null3)

    def retune(self, freq):
        self._retune(freq)

    def power_dbfs(self):
        p = self.pwr_probe.level()
        return 10.0 * math.log10(p) if p > 1e-12 else -120.0

    def lock_metric(self):
        if not self.have_lock:
            return 0.0
        return self.lock_probe.level()


def main():
    ap = argparse.ArgumentParser(description="Headless FPV signal detector")
    ap.add_argument('--sdr', default='uhd')
    ap.add_argument('--samp-rate', type=float, default=10e6)
    ap.add_argument('--gain', type=float, default=40.0)
    ap.add_argument('--dev-args', default='')
    ap.add_argument('--antenna', default=None)
    ap.add_argument('--power-thresh', type=float, default=-50.0)
    ap.add_argument('--lock-thresh', type=float, default=0.5)
    ap.add_argument('--settle', type=float, default=0.35)
    ap.add_argument('--lock-dwell', type=float, default=0.7)
    ap.add_argument('--continuous', action='store_true')
    ap.add_argument('--stop-on-hit', action='store_true')
    ap.add_argument('channels', nargs='+')
    args = ap.parse_args()

    chans = []
    for tok in args.channels:
        name, _, fhz = tok.partition(':')
        if not fhz:
            sys.stderr.write("[detect] bad channel token: %s\n" % tok)
            continue
        chans.append((name, float(fhz)))
    if not chans:
        sys.stderr.write("[detect] no valid channels\n")
        return 2

    if not HAVE_NTSC:
        sys.stderr.write(
            "[detect] gnuradio.NTSC not built — power-only survey, no sync-lock "
            "gating (build gr-ntsc-rc to enable lock confirmation)\n")

    tb = detector(args.sdr, args.samp_rate, args.gain,
                  chans[0][1], args.dev_args, args.antenna)

    def _clean_exit(sig=None, frame=None):
        tb.stop()
        tb.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, _clean_exit)
    signal.signal(signal.SIGTERM, _clean_exit)

    tb.start()

    rc = 1
    try:
        first_pass = True
        while first_pass or args.continuous:
            first_pass = False
            for name, freq in chans:
                tb.retune(freq)
                time.sleep(args.settle)
                pwr = tb.power_dbfs()
                lock = 0
                if pwr >= args.power_thresh and tb.have_lock:
                    time.sleep(args.lock_dwell)
                    pwr = tb.power_dbfs()
                    lock = 1 if tb.lock_metric() >= args.lock_thresh else 0
                if lock:
                    status = 'LOCK'
                elif pwr >= args.power_thresh:
                    status = 'carrier'
                else:
                    status = 'no'
                print("DETECT %s %.0f %.1f %d %s" % (name, freq, pwr, lock, status),
                      flush=True)
                if lock:
                    print("HIT %s %.0f" % (name, freq), flush=True)
                    rc = 0
                    if args.stop_on_hit:
                        return rc
    except KeyboardInterrupt:
        pass
    finally:
        tb.stop()
        tb.wait()
    return rc


if __name__ == '__main__':
    sys.exit(main())
