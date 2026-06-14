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

from fpv_sdr import build_source, quad_demod_gain, UHD_ALIASES
import fpv_spectrum


def integrate_psd(psd, center, samp_rate, freq, in_bw, sh_bw):
    n = len(psd)
    p_in = 0.0
    p_sh = 0.0
    ic = 0
    sc = 0
    if n == 0:
        return p_in, ic, p_sh, sc
    binhz = samp_rate / n
    for k in range(n):
        koff = k - n / 2.0
        if -2.0 <= koff <= 2.0:
            continue
        d = abs((center + koff * binhz) - freq)
        if d <= in_bw / 2.0:
            p_in += psd[k]
            ic += 1
        elif d <= sh_bw / 2.0:
            p_sh += psd[k]
            sc += 1
    return p_in, ic, p_sh, sc


def psd_floor(bins, frac=0.2):
    if not bins:
        return 1e-12
    s = sorted(bins)
    idx = int(len(s) * frac)
    if idx >= len(s):
        idx = len(s) - 1
    return s[idx]


def cv_from_moments(m1, m2):
    if m1 <= 1e-9:
        return 1.0
    var = m2 - m1 * m1
    if var < 0.0:
        var = 0.0
    return math.sqrt(var) / m1


def chunk_plan(freqs, usable):
    fs = sorted(set(freqs))
    chunks = []
    i = 0
    n = len(fs)
    while i < n:
        lo = fs[i]
        j = i
        while j < n and fs[j] - lo <= usable:
            j += 1
        chunks.append((lo + fs[j - 1]) / 2.0)
        i = j
    return chunks


class detector(gr.top_block):
    def __init__(self, sdr, samp_rate, gain, start_freq, dev_args, antenna,
                 loc_nfft=4096, loc_margin=6.0, lna=None, vga=None, amp=False,
                 want_lock=True):
        gr.top_block.__init__(self, "FPV Detector", catch_exceptions=True)
        self.samp_rate = samp_rate
        self.is_hackrf = (str(sdr).lower() == 'hackrf')
        self.is_uhd = (str(sdr).lower() in UHD_ALIASES)

        self.src, self._retune = build_source(
            samp_rate, start_freq, gain, sdr=sdr, dev_args=dev_args, antenna=antenna,
            lna=lna, vga=vga, amp=amp)

        pwr_win = max(1, int(samp_rate * 0.005))
        lock_win = max(1, int(samp_rate * 0.02))

        self.have_lock = HAVE_NTSC and not self.is_hackrf and want_lock

        self.dcblock = filter.dc_blocker_cc(32, True)
        self.connect(self.src, self.dcblock)

        self.cvlpf = filter.fir_filter_ccf(
            1, firdes.low_pass(1, samp_rate, 9e6, 3e6, window.WIN_HAMMING, 6.76))
        self.connect(self.dcblock, self.cvlpf)

        self.mag2 = blocks.complex_to_mag_squared(1)
        self.pwr_avg = blocks.moving_average_ff(pwr_win, 1.0 / pwr_win, 4000, 1)
        self.pwr_probe = blocks.probe_signal_f()
        self.connect(self.cvlpf, self.mag2, self.pwr_avg, self.pwr_probe)

        self.mag = blocks.complex_to_mag(1)
        self.mag_avg = blocks.moving_average_ff(pwr_win, 1.0 / pwr_win, 4000, 1)
        self.mag_probe = blocks.probe_signal_f()
        self.connect(self.cvlpf, self.mag, self.mag_avg, self.mag_probe)

        self.center = start_freq
        self.loc_nfft = loc_nfft
        self.loc_margin = loc_margin
        win = window.blackmanharris(loc_nfft)
        wpow = sum(w * w for w in win)
        self.fft_norm_db = 10.0 * math.log10(wpow) if wpow > 0.0 else 0.0
        self.s2v = blocks.stream_to_vector(gr.sizeof_gr_complex, loc_nfft)
        self.fftc = gr_fft.fft_vcc(
            loc_nfft, True, win, True, 1)
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

    def envelope_cv(self, dwell, interval=0.02):
        m1 = 0.0
        m2 = 0.0
        n = 0
        end = time.time() + dwell
        while time.time() < end:
            time.sleep(interval)
            m1 += self.mag_probe.level()
            m2 += self.pwr_probe.level()
            n += 1
        if n == 0:
            m1 = self.mag_probe.level()
            m2 = self.pwr_probe.level()
            n = 1
        return cv_from_moments(m1 / n, m2 / n)

    def lock_metric(self):
        if not self.have_lock:
            return 0.0
        return self.lock_probe.level()

    def read_psd(self, dwell):
        time.sleep(dwell)
        return self.vprobe.level()

    def band_spectrum(self, lo, hi, usable, dwell, settle, width, peak=False):
        span = hi - lo
        if span <= 0 or width <= 0:
            return [None] * max(0, width), -120.0
        sums = [0.0] * width
        cnts = [0] * width
        peaks = [0.0] * width
        half_u = usable / 2.0
        floor_bins = []
        c = lo + usable / 2.0
        centers = []
        while c < hi + usable / 2.0:
            centers.append(c)
            c += usable
        for cc in centers:
            self.retune(cc)
            time.sleep(settle)
            psd = self.read_psd(dwell)
            n = len(psd)
            if n == 0:
                continue
            binhz = self.samp_rate / n
            for k in range(n):
                koff = k - n / 2.0
                if -2.0 <= koff <= 2.0:
                    continue
                if abs(koff * binhz) > half_u:
                    continue
                f = cc + koff * binhz
                if f < lo or f >= hi:
                    continue
                col = int((f - lo) / span * width)
                if col < 0 or col >= width:
                    continue
                p = psd[k]
                if p <= 1e-15:
                    continue
                sums[col] += p
                cnts[col] += 1
                if p > peaks[col]:
                    peaks[col] = p
                floor_bins.append(p)
        cols = []
        for i in range(width):
            if cnts[i] == 0:
                cols.append(None)
                continue
            val = peaks[i] if peak else sums[i] / cnts[i]
            cols.append((10.0 * math.log10(val) - self.fft_norm_db)
                        if val > 1e-15 else None)
        floor_db = -120.0
        if floor_bins:
            floor_bins.sort()
            fl = floor_bins[int(len(floor_bins) * 0.2)]
            if fl > 1e-15:
                floor_db = 10.0 * math.log10(fl) - self.fft_norm_db
        return cols, floor_db

    def survey(self, chans, usable, dwell, settle, in_bw, sh_bw):
        uniq = sorted(set(f for _, f in chans))
        centers = chunk_plan(uniq, usable)
        half_u = usable / 2.0
        assign = {}
        for f in uniq:
            best = None
            for c in centers:
                d = abs(f - c)
                if d <= half_u and (best is None or d < best[0]):
                    best = (d, c)
            if best is not None:
                assign[f] = best[1]
        per_freq = {}
        floor_bins = []
        for c in centers:
            mine = [f for f in uniq if assign.get(f) == c]
            if not mine:
                continue
            self.retune(c)
            time.sleep(settle)
            psd = self.read_psd(dwell)
            n = len(psd)
            if n == 0:
                continue
            binhz = self.samp_rate / n
            for f in mine:
                per_freq[f] = integrate_psd(psd, c, self.samp_rate, f, in_bw, sh_bw)
            for k in range(n):
                koff = k - n / 2.0
                if -2.0 <= koff <= 2.0:
                    continue
                if abs(koff * binhz) <= half_u:
                    floor_bins.append(psd[k])
        return per_freq, psd_floor(floor_bins)

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
    ap.add_argument('--samp-rate', type=float, default=20e6)
    ap.add_argument('--gain', type=float, default=40.0)
    ap.add_argument('--lna', type=float, default=None,
                    help='hackrf LNA (IF) gain dB 0-40 step 8 (default 24)')
    ap.add_argument('--vga', type=float, default=None,
                    help='hackrf VGA (baseband) gain dB 0-62 step 2 (default 20)')
    ap.add_argument('--amp', action='store_true',
                    help='hackrf +14 dB front-end amp (OFF by default; strong signals can damage the LNA)')
    ap.add_argument('--dev-args', default='')
    ap.add_argument('--antenna', default=None)
    ap.add_argument('--power-thresh', type=float, default=-50.0)
    ap.add_argument('--lock-thresh', type=float, default=1.0)
    ap.add_argument('--margin', type=float, default=12.0,
                    help='min SNR (dB over the noise floor) for a channel to be a candidate')
    ap.add_argument('--peak-thresh', type=float, default=3.0,
                    help='min in-band minus shoulder power (dB) — rejects broadband Wi-Fi')
    ap.add_argument('--env-cv', type=float, default=0.35,
                    help='hackrf: max in-band envelope CV to accept (analog FPV is near-constant-envelope FM)')
    ap.add_argument('--confirm', choices=('auto', 'cv', 'ntsc', 'snr'), default='auto',
                    help='carrier confirm: auto (FM envelope-CV gate, plus NTSC sync-lock '
                         'as an ADDITIVE second pass where the decoder is built — lock can '
                         'only help accept, never reject); cv (force CV only); ntsc (force '
                         'NTSC-lock only); snr (SNR+narrow-peak only, no carrier confirm)')
    ap.add_argument('--usable-frac', type=float, default=0.8,
                    help='fraction of the sample rate kept per FFT chunk (drops rolled-off band edges)')
    ap.add_argument('--in-bw', type=float, default=10e6,
                    help='in-band integration width in Hz for per-channel power')
    ap.add_argument('--sh-bw', type=float, default=18e6,
                    help='outer shoulder-ring width in Hz for the narrow-peak test')
    ap.add_argument('--chunk-dwell', type=float, default=0.12,
                    help='seconds of averaged FFT captured per chunk during the sweep')
    ap.add_argument('--localize-dwell', type=float, default=0.3,
                    help='seconds of averaged FFT per pass to find the true '
                         'carrier center (0 disables; picks the strongest candidate)')
    ap.add_argument('--localize-iters', type=int, default=3,
                    help='re-center the FFT window on the measured center N times')
    ap.add_argument('--settle', type=float, default=0.2)
    ap.add_argument('--lock-dwell', type=float, default=0.5)
    ap.add_argument('--survey-only', action='store_true',
                    help='print the per-channel RSSI survey and exit (no gating, no HIT)')
    ap.add_argument('--spectrum', action='store_true',
                    help='draw a terminal FFT spectrum of the band and exit')
    ap.add_argument('--spec-lo', type=float, default=None,
                    help='spectrum span low edge in Hz (default: lowest channel - 8 MHz)')
    ap.add_argument('--spec-hi', type=float, default=None,
                    help='spectrum span high edge in Hz (default: highest channel + 8 MHz)')
    ap.add_argument('--spec-center', type=float, default=None,
                    help='single-span live spectrum centered here in Hz (one FFT window, fast redraw)')
    ap.add_argument('--spec-width', type=int, default=0,
                    help='spectrum columns (0 = 80)')
    ap.add_argument('--spec-height', type=int, default=16,
                    help='spectrum rows')
    ap.add_argument('--spec-min', type=float, default=None,
                    help='spectrum dBFS floor of the colour/height scale (auto if unset)')
    ap.add_argument('--spec-max', type=float, default=None,
                    help='spectrum dBFS top of the colour/height scale (auto if unset)')
    ap.add_argument('--no-color', action='store_true',
                    help='disable ANSI colour in the spectrum')
    ap.add_argument('--spec-peak', action='store_true',
                    help='peak-hold the spectrum (catch bursts) instead of averaging each column')
    ap.add_argument('--spec-interval', type=float, default=0.0,
                    help='seconds to pause between live spectrum redraws (0 = redraw immediately)')
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

    if not HAVE_NTSC and (args.sdr or '').lower() in UHD_ALIASES \
            and args.confirm in ('auto', 'ntsc'):
        sys.stderr.write(
            "[detect] gnuradio.NTSC not built — UHD carrier confirm falls back to "
            "SNR+narrow-peak only (build gr-ntsc-rc to enable NTSC sync-lock)\n")

    want_lock = (not args.spectrum and not args.survey_only
                 and args.confirm == 'ntsc')
    tb = detector(args.sdr, args.samp_rate, args.gain,
                  chans[0][1], args.dev_args, args.antenna,
                  lna=args.lna, vga=args.vga, amp=args.amp,
                  want_lock=want_lock)

    def _clean_exit(sig=None, frame=None):
        tb.stop()
        tb.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, _clean_exit)
    signal.signal(signal.SIGTERM, _clean_exit)

    tb.start()

    confirm = args.confirm
    if confirm == 'auto':
        confirm = 'cv'

    usable = args.samp_rate * args.usable_frac
    n_chunks = len(chunk_plan([f for _, f in chans], usable))

    if args.spectrum:
        if args.spec_center:
            half = args.samp_rate / 2.0
            lo = args.spec_center - half
            hi = args.spec_center + half
            spec_usable = args.samp_rate
        else:
            lo = args.spec_lo if args.spec_lo else (min(f for _, f in chans) - 8e6)
            hi = args.spec_hi if args.spec_hi else (max(f for _, f in chans) + 8e6)
            spec_usable = usable
        width = args.spec_width if args.spec_width > 0 else 80
        try:
            while True:
                cols, floor_db = tb.band_spectrum(
                    lo, hi, spec_usable, args.chunk_dwell, args.settle, width,
                    peak=args.spec_peak)
                title = ("FPV spectrum  %.0f-%.0f MHz  floor %.0f dBFS  [%s]"
                         % (lo / 1e6, hi / 1e6, floor_db, args.sdr))
                art = fpv_spectrum.render(
                    cols, lo, hi, floor_db, height=args.spec_height,
                    dmin=args.spec_min, dmax=args.spec_max,
                    color=(not args.no_color), title=title)
                if args.continuous:
                    sys.stdout.write("\x1b[2J\x1b[H")
                sys.stdout.write(art + "\n")
                sys.stdout.flush()
                if not args.continuous:
                    break
                if args.spec_interval > 0:
                    time.sleep(args.spec_interval)
        except KeyboardInterrupt:
            pass
        finally:
            tb.stop()
            tb.wait()
        return 0

    rc = 1
    try:
        while True:
            per_freq, floor_lin = tb.survey(
                chans, usable, args.chunk_dwell, args.settle,
                args.in_bw, args.sh_bw)
            floor_db = (10.0 * math.log10(floor_lin) - tb.fft_norm_db) \
                if floor_lin > 1e-15 else -120.0

            rows = []
            for name, freq in chans:
                pf = per_freq.get(freq)
                if pf is None:
                    continue
                p_in, ic, p_sh, sc = pf
                pin_avg = (p_in / ic) if ic else 0.0
                psh_avg = (p_sh / sc) if sc else floor_lin
                pin_db = (10.0 * math.log10(pin_avg) - tb.fft_norm_db) \
                    if pin_avg > 1e-15 else -120.0
                snr = pin_db - floor_db
                if pin_avg > 1e-15 and psh_avg > 1e-15:
                    peak = 10.0 * math.log10(pin_avg / psh_avg)
                else:
                    peak = 0.0
                rows.append((name, freq, pin_db, snr, peak))
                if args.debug:
                    sys.stderr.write("DBG %s snr=%.1f peak=%.1f\n"
                                     % (name, snr, peak))
                print("DETECT %s %.0f %.1f 0 fft" % (name, freq, pin_db),
                      flush=True)

            sys.stderr.write(
                "[detect] noise floor %.1f dBFS over %d FFT chunk(s); "
                "SNR gate %.0f dB, peak gate %.0f dB\n"
                % (floor_db, n_chunks, args.margin, args.peak_thresh))

            if args.survey_only:
                rc = 0 if rows else 1
                break

            cands = [r for r in rows
                     if r[3] >= args.margin and r[4] >= args.peak_thresh]
            cands.sort(key=lambda r: -r[3])
            hit_names = {r[0] for r in cands}

            hit = None
            for cand in cands[:3]:
                seed = cand[1]
                if args.localize_dwell > 0:
                    center = tb.localize_center(
                        seed, args.localize_dwell, args.settle,
                        iters=args.localize_iters)
                    if center is None or \
                            abs(center - seed) > args.samp_rate / 2.0:
                        center = seed
                else:
                    center = seed
                name, freq = nearest_channel(chans, center, hit_names)
                tb.retune(center)
                time.sleep(args.settle)
                cv = None
                lk = None
                if confirm == 'cv':
                    cv = tb.envelope_cv(args.lock_dwell)
                elif confirm == 'ntsc' and tb.have_lock:
                    time.sleep(args.lock_dwell)
                    lk = tb.lock_metric()
                cv_ok = cv is not None and cv <= args.env_cv
                lk_ok = lk is not None and lk >= args.lock_thresh
                if confirm == 'cv':
                    ok = cv_ok
                elif confirm == 'ntsc':
                    ok = lk_ok
                else:
                    ok = True
                parts = []
                if cv is not None:
                    parts.append("env-CV %.2f%s" % (cv, " ok" if cv_ok else " no"))
                if lk is not None:
                    parts.append("NTSC-lock %.2f%s" % (lk, " ok" if lk_ok else " no"))
                mlabel = " + ".join(parts) if parts else "SNR+peak only"
                print("DETECT CENTER %.0f %.1f 0 fft" % (center, cand[2]),
                      flush=True)
                sys.stderr.write(
                    "[detect] candidate %s: center %.3f MHz -> %s %.0f MHz "
                    "(%+.2f MHz off), SNR %.1f dB, %s -> %s\n"
                    % (cand[0], center / 1e6, name, freq / 1e6,
                       (center - freq) / 1e6, cand[3], mlabel,
                       "ACCEPT" if ok else "REJECT"))
                if ok:
                    print("HIT %s %.0f %.1f" % (name, freq, cand[3]),
                          flush=True)
                    rc = 0
                    hit = (name, freq)
                    break

            if hit is None:
                if cands:
                    sys.stderr.write(
                        "[detect] %d candidate(s) over the floor but none "
                        "confirmed as a valid FPV carrier\n" % len(cands))
                else:
                    sys.stderr.write("[detect] no channel above the SNR gate\n")

            if (hit and args.stop_on_hit) or not args.continuous:
                break
    except KeyboardInterrupt:
        pass
    finally:
        tb.stop()
        tb.wait()
    return rc


if __name__ == '__main__':
    sys.exit(main())
