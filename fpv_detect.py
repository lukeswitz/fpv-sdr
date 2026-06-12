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
from gnuradio import fft as gr_fft
from gnuradio.fft import window

try:
    import gnuradio.NTSC as NTSC
    HAVE_NTSC = True
except Exception:
    NTSC = None
    HAVE_NTSC = False

from fpv_sdr import build_source, quad_demod_gain


class detector(gr.top_block):
    def __init__(self, sdr, samp_rate, gain, start_freq, dev_args, antenna,
                 loc_nfft=4096, loc_margin=6.0):
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

        self.center = start_freq
        self.loc_nfft = loc_nfft
        self.loc_margin = loc_margin
        self.s2v = blocks.stream_to_vector(gr.sizeof_gr_complex, loc_nfft)
        self.fftc = gr_fft.fft_vcc(
            loc_nfft, True, window.blackmanharris(loc_nfft), True, 1)
        self.fmag2 = blocks.complex_to_mag_squared(loc_nfft)
        self.favg = filter.single_pole_iir_filter_ff(0.005, loc_nfft)
        self.vprobe = blocks.probe_signal_vf(loc_nfft)
        self.connect(self.dcblock, self.s2v, self.fftc,
                     self.fmag2, self.favg, self.vprobe)

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
        self.center = freq

    def power_dbfs(self):
        p = self.pwr_probe.level()
        return 10.0 * math.log10(p) if p > 1e-12 else -120.0

    def power_dbfs_avg(self, dwell, interval=0.03):
        acc = 0.0
        n = 0
        end = time.time() + dwell
        while time.time() < end:
            time.sleep(interval)
            acc += self.pwr_probe.level()
            n += 1
        if n == 0:
            return self.power_dbfs()
        mean = acc / n
        return 10.0 * math.log10(mean) if mean > 1e-12 else -120.0

    def lock_metric(self):
        if not self.have_lock:
            return 0.0
        return self.lock_probe.level()

    def spectrum_center(self, dwell):
        time.sleep(dwell)
        psd = self.vprobe.level()
        n = len(psd)
        if n == 0:
            return None
        s = sorted(psd)
        peak = s[-1]
        if peak <= 0.0:
            return None
        floor = s[max(0, n // 20)]
        if peak <= floor * (10.0 ** (self.loc_margin / 10.0)):
            return None
        num = 0.0
        den = 0.0
        for k in range(n):
            w = psd[k] - floor
            if w > 0.0:
                num += k * w
                den += w
        if den <= 0.0:
            return None
        cbin = num / den
        return self.center + (cbin - n / 2.0) * self.samp_rate / n

    def localize_center(self, init_freq, dwell, settle, iters=2):
        c = init_freq
        last = None
        for _ in range(max(1, iters)):
            self.retune(c)
            time.sleep(settle)
            m = self.spectrum_center(dwell)
            if m is None:
                return last
            last = m
            c = m
        return last


def nearest_channel(chans, center_hz, hit_names):
    best = None
    for i, (name, freq) in enumerate(chans):
        key = (abs(freq - center_hz), 0 if name in hit_names else 1, i)
        if best is None or key < best[0]:
            best = (key, name, freq)
    return best[1], best[2]


def main():
    ap = argparse.ArgumentParser(description="Headless FPV signal detector")
    ap.add_argument('--sdr', default='uhd')
    ap.add_argument('--samp-rate', type=float, default=10e6)
    ap.add_argument('--gain', type=float, default=40.0)
    ap.add_argument('--dev-args', default='')
    ap.add_argument('--antenna', default=None)
    ap.add_argument('--power-thresh', type=float, default=-50.0)
    ap.add_argument('--lock-thresh', type=float, default=0.5)
    ap.add_argument('--margin', type=float, default=6.0,
                    help='dB above the median noise floor to call a channel a hit')
    ap.add_argument('--localize-dwell', type=float, default=0.3,
                    help='seconds of averaged FFT per pass to find the true '
                         'carrier center (0 disables; falls back to power rank)')
    ap.add_argument('--localize-iters', type=int, default=3,
                    help='re-center the FFT window on the measured center N times')
    ap.add_argument('--settle', type=float, default=0.35)
    ap.add_argument('--lock-dwell', type=float, default=0.7)
    ap.add_argument('--continuous', action='store_true')
    ap.add_argument('--stop-on-hit', action='store_true')
    ap.add_argument('--debug', action='store_true')
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
                  chans[0][1], args.dev_args, args.antenna,
                  loc_margin=args.margin)

    def _clean_exit(sig=None, frame=None):
        tb.stop()
        tb.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, _clean_exit)
    signal.signal(signal.SIGTERM, _clean_exit)

    tb.start()

    rc = 1
    try:
        while True:
            results = []
            for name, freq in chans:
                tb.retune(freq)
                time.sleep(args.settle)
                pwr = tb.power_dbfs()
                results.append((name, freq, pwr))
                if args.debug and tb.have_lock:
                    sys.stderr.write("DBG %s pwr=%.1f lockmetric=%.3f\n"
                                     % (name, pwr, tb.lock_metric()))
                print("DETECT %s %.0f %.1f 0 scan" % (name, freq, pwr), flush=True)

            powers = sorted(p for _, _, p in results)
            floor = powers[len(powers) // 2]
            hits = sorted((r for r in results if r[2] >= floor + args.margin),
                          key=lambda r: -r[2])
            sys.stderr.write("[detect] noise floor %.1f dBFS; %d channel(s) >= floor+%.0f dB\n"
                             % (floor, len(hits), args.margin))
            hit_names = {r[0] for r in hits}
            center_hz = None
            if hits and args.localize_dwell > 0:
                seed = hits[0][1]
                center_hz = tb.localize_center(
                    seed, args.localize_dwell, args.settle,
                    iters=args.localize_iters)
                if center_hz is not None and \
                        abs(center_hz - seed) > args.samp_rate / 2.0:
                    center_hz = seed
            if center_hz is not None:
                name, freq = nearest_channel(chans, center_hz, hit_names)
                disp = hits[0][2]
                print("DETECT CENTER %.0f %.1f 0 fft" % (center_hz, disp),
                      flush=True)
                sys.stderr.write(
                    "[detect] measured center %.3f MHz -> %s %.0f MHz "
                    "(%+.2f MHz off nominal)\n"
                    % (center_hz / 1e6, name, freq / 1e6,
                       (center_hz - freq) / 1e6))
                print("HIT %s %.0f %.1f" % (name, freq, disp - floor),
                      flush=True)
                rc = 0
            else:
                for name, freq, pwr in hits:
                    print("HIT %s %.0f %.1f" % (name, freq, pwr - floor),
                          flush=True)
                    rc = 0
            if (hits and args.stop_on_hit) or not args.continuous:
                break
    except KeyboardInterrupt:
        pass
    finally:
        tb.stop()
        tb.wait()
    return rc


if __name__ == '__main__':
    sys.exit(main())
