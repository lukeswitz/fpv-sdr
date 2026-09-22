#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0

import os
import sys
import math
import time
import shutil
import signal
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gnuradio import gr, analog, blocks, filter
from gnuradio.filter import firdes
from gnuradio.fft import window

try:
    import gnuradio.NTSC as NTSC
    HAVE_NTSC = True
except Exception:
    NTSC = None
    HAVE_NTSC = False

try:
    from gnuradio import video_sdl
    HAVE_SDL = True
except Exception:
    video_sdl = None
    HAVE_SDL = False

from fpv_sdr import build_source, quad_demod_gain, UHD_ALIASES
from fpv_display import frame_sink

LOCK_FULL = 5.0

SYNC_THRESHOLD = -0.020
SYNC_MID = -0.0273


def level_offset(contrast, sync_mid=SYNC_MID):
    return SYNC_THRESHOLD - sync_mid * contrast


def split_gain(total, lna_max=32.0):
    lna = max(0.0, min(float(lna_max), float(int(total) // 8 * 8)))
    vga = max(0.0, min(62.0, round((float(total) - lna) / 2.0) * 2.0))
    return lna, vga


class viewer(gr.top_block):
    def __init__(self, sdr, samp_rate, freq, gain, dev_args, antenna,
                 frame_out='/tmp/fpv_frame.png', record_path=None, live=True, dcblock=True,
                 rotate=0, oversample=2, contrast=1.0, lna=None, vga=None, amp=False,
                 standard='ntsc', display='auto', video_offset=None, video_bw=1.25e6,
                 sync_mid=SYNC_MID, agc=False, agc_target=-20.0, agc_lna_max=32.0,
                 if_offset=0.0):
        gr.top_block.__init__(self, "FPV Viewer", catch_exceptions=True)
        self.samp_rate = samp_rate
        self.frequency_carrier = freq

        is_pal = str(standard).lower() == 'pal'
        self.vid_w, self.vid_h, field_rate, std_code = (
            (360, 288, 50, 1) if is_pal else (360, 240, 60, 0))

        oversample = max(1, int(oversample))
        self.cap_rate = cap_rate = samp_rate * oversample
        video_bw = float(video_bw)
        self.if_offset = float(if_offset)
        if self.if_offset and abs(self.if_offset) > cap_rate / 2.0 - video_bw:
            self.if_offset = 0.0
        self.src, self._retune = build_source(
            cap_rate, freq + self.if_offset, gain, sdr=sdr, dev_args=dev_args,
            antenna=antenna, lna=lna, vga=vga, amp=amp)

        title = 'FPV-SDR %.0f MHz' % (freq / 1e6)
        self.low_pass_filter_1 = filter.fir_filter_fff(
            oversample,
            firdes.low_pass(1, cap_rate, video_bw, video_bw, window.WIN_HAMMING, 6.76))
        self.analog_quadrature_demod_cf_0 = analog.quadrature_demod_cf(
            quad_demod_gain(cap_rate) * contrast)
        self.NTSC_decoder_c_0 = NTSC.decoder_c(samp_rate, std_code)

        if sdr.lower() in UHD_ALIASES or not dcblock:
            tail = (self.src, 0)
        else:
            self.dcblock = filter.dc_blocker_cc(32, False)
            self.connect((self.src, 0), self.dcblock)
            tail = self.dcblock
        if self.if_offset:
            self.if_lo = analog.sig_source_c(cap_rate, analog.GR_COS_WAVE,
                                             self.if_offset, 1.0, 0.0)
            self.if_mix = blocks.multiply_cc(1)
            self.connect(tail, (self.if_mix, 0))
            self.connect(self.if_lo, (self.if_mix, 1))
            tail = self.if_mix
        self.connect(tail, (self.analog_quadrature_demod_cf_0, 0))
        self.connect((self.analog_quadrature_demod_cf_0, 0), (self.low_pass_filter_1, 0))
        self.sync_mid = float(sync_mid)
        self.video_offset = (level_offset(contrast, self.sync_mid)
                             if video_offset is None else float(video_offset))
        self.video_level = blocks.add_const_ff(self.video_offset)
        self.connect((self.low_pass_filter_1, 0), self.video_level)
        self.connect(self.video_level, (self.NTSC_decoder_c_0, 0))

        self.NTSC_video_stream_converter_c_0 = NTSC.video_stream_converter_c(
            samp_rate, samp_rate / (self.vid_w * self.vid_h * field_rate),
            self.vid_w, self.vid_h)
        self.connect((self.NTSC_decoder_c_0, 0), (self.NTSC_video_stream_converter_c_0, 0))
        self.connect((self.NTSC_decoder_c_0, 1), (self.NTSC_video_stream_converter_c_0, 1))
        self.connect((self.NTSC_decoder_c_0, 2), (self.NTSC_video_stream_converter_c_0, 2))
        self.connect((self.NTSC_decoder_c_0, 3), (self.NTSC_video_stream_converter_c_0, 3))

        self.frame_px = self.vid_w * self.vid_h
        self.line_px = self.vid_w
        self.sync_center = self.frame_px
        self.sync_off = self.sync_center
        self.v_lines = 0
        self.h_px = 0
        self.sync_delay = blocks.delay(gr.sizeof_short, self.sync_center)
        self.connect((self.NTSC_video_stream_converter_c_0, 0), (self.sync_delay, 0))

        lock_dec = max(1, int(samp_rate / 100e3))
        lock_win = max(1, int(samp_rate * 0.02) // lock_dec)
        self.lock_state = blocks.add_const_ff(-1.0)
        self.lock_abs = blocks.abs_ff(1)
        self.lock_keep = blocks.keep_one_in_n(gr.sizeof_float, lock_dec)
        self.lock_avg = blocks.moving_average_ff(lock_win, 1.0 / lock_win, 4000, 1)
        self.lock_probe = blocks.probe_signal_f()
        self.connect((self.NTSC_decoder_c_0, 0), self.lock_state,
                     self.lock_abs, self.lock_keep, self.lock_avg, self.lock_probe)

        self.agc = bool(agc)
        self.agc_target = float(agc_target)
        self.agc_lna_max = float(agc_lna_max)
        self.agc_total = float(gain if lna is None else lna) + float(gain if vga is None else vga)
        self._agc_next = 0.0
        if self.agc:
            l0, v0 = split_gain(self.agc_total, self.agc_lna_max)
            self.agc_total = l0 + v0
            try:
                self.src.set_gain(0, 'LNA', l0)
                self.src.set_gain(0, 'VGA', v0)
            except (AttributeError, RuntimeError):
                self.agc = False
        lvl_dec = max(1, int(cap_rate / 100e3))
        self.lvl_mag = blocks.complex_to_mag_squared(1)
        self.lvl_keep = blocks.keep_one_in_n(gr.sizeof_float, lvl_dec)
        lvl_win = max(1, int(cap_rate * 0.05) // lvl_dec)
        self.lvl_avg = blocks.moving_average_ff(lvl_win, 1.0 / lvl_win, 4000, 1)
        self.lvl_probe = blocks.probe_signal_f()
        self.connect((self.src, 0), self.lvl_mag, self.lvl_keep,
                     self.lvl_avg, self.lvl_probe)

        self.recorder = None
        self.frame_sink_0 = None
        display = str(display).lower()
        if display == 'auto':
            display = 'sdl' if (HAVE_SDL and not shutil.which('ffplay')) else 'ffplay'
        if HAVE_SDL and live and display in ('sdl', 'sdl-hw'):
            if display != 'sdl-hw':
                os.environ.setdefault('SDL_VIDEO_YUV_HWACCEL', '0')
            self.video_sdl_sink_0 = video_sdl.sink_s(
                0, self.vid_w, self.vid_h, (self.vid_w * 2), (self.vid_h * 2))
            self.connect((self.sync_delay, 0), (self.video_sdl_sink_0, 0))
            if record_path:
                self.recorder = frame_sink(self.vid_w, self.vid_h, None, record_path=record_path, rotate=rotate)
                self.connect((self.sync_delay, 0), (self.recorder, 0))
        else:
            self.frame_sink_0 = frame_sink(
                self.vid_w, self.vid_h, None if live else frame_out,
                record_path=record_path, live=live, title=title, rotate=rotate)
            self.connect((self.sync_delay, 0), (self.frame_sink_0, 0))

    def retune(self, freq):
        self.frequency_carrier = freq
        self._retune(freq + self.if_offset)

    def set_contrast(self, contrast):
        self.analog_quadrature_demod_cf_0.set_gain(quad_demod_gain(self.cap_rate) * contrast)
        self.set_video_offset(level_offset(contrast, self.sync_mid))

    def set_video_offset(self, offset):
        self.video_offset = float(offset)
        self.video_level.set_k(self.video_offset)

    def _apply_sync(self):
        off = self.sync_center + self.v_lines * self.line_px + self.h_px
        self.sync_off = max(0, min(2 * self.frame_px, off))
        self.sync_delay.set_dly(self.sync_off)

    def reset_sync(self):
        self.v_lines = 0
        self.h_px = 0
        self._apply_sync()

    def nudge_v(self, lines):
        self.v_lines = max(-(self.vid_h - 1), min(self.vid_h - 1, self.v_lines + lines))
        self._apply_sync()

    def nudge_h(self, px):
        self.h_px = max(-(self.line_px - 1), min(self.line_px - 1, self.h_px + px))
        self._apply_sync()

    def sync_status(self):
        return self.v_lines, self.h_px

    def rf_dbfs(self):
        p = self.lvl_probe.level()
        return 10.0 * math.log10(p) if p > 1e-12 else -120.0

    def update_agc(self):
        rms = self.rf_dbfs()
        now = time.monotonic()
        if not self.agc or now < self._agc_next or rms <= -119.0:
            return rms
        self._agc_next = now + 0.4
        err = self.agc_target - rms
        if abs(err) < 1.0:
            return rms
        total = max(0.0, min(102.0, self.agc_total + max(-10.0, min(10.0, err))))
        lna, vga = split_gain(total, self.agc_lna_max)
        if (lna, vga) != self.agc_gains():
            try:
                self.src.set_gain(0, 'LNA', lna)
                self.src.set_gain(0, 'VGA', vga)
            except (AttributeError, RuntimeError):
                self.agc = False
                return rms
        self.agc_total = total
        return rms

    def agc_gains(self):
        return split_gain(self.agc_total, self.agc_lna_max)

    def lock_metric(self):
        return self.lock_probe.level()

    def lock_pct(self):
        return max(0, min(100, int(self.lock_probe.level() / LOCK_FULL * 100)))

    def window_closed(self):
        return self.frame_sink_0 is not None and self.frame_sink_0.closed


def keys_available():
    if not sys.stdin.isatty():
        return False
    try:
        import termios  # noqa: F401
        return os.tcgetpgrp(sys.stdin.fileno()) == os.getpgrp()
    except (ImportError, OSError):
        return False


def _parse_keys(buf):
    s = buf.decode('latin-1')
    arrows = {'A': 'up', 'B': 'down', 'C': 'right', 'D': 'left'}
    keys = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == '\x1b':
            if s[i + 1:i + 2] in ('[', 'O'):
                keys.append(arrows.get(s[i + 2:i + 3], ''))
                i += 3
            else:
                i += 1
        else:
            keys.append(c)
            i += 1
    return [k for k in keys if k]


def run_sync_tuner(tb):
    import termios
    import select
    import tempfile

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    errlog = tempfile.TemporaryFile()
    saved_err = os.dup(2)
    sys.stderr.flush()
    os.dup2(errlog.fileno(), 2)
    sys.stderr.write(
        "[fpv] sync tuner: up/down = vertical hold, left/right = horizontal, "
        "r = reset, q = quit\n")
    try:
        raw = termios.tcgetattr(fd)
        raw[3] = raw[3] & ~(termios.ICANON | termios.ECHO)
        termios.tcsetattr(fd, termios.TCSANOW, raw)
        sys.stdout.write("\x1b[?1l\x1b[?1004l\x1b[?1000l\x1b[?1003l")
        sys.stdout.flush()
        while not tb.window_closed():
            r, _, _ = select.select([fd], [], [], 0.2)
            if r:
                for key in _parse_keys(os.read(fd, 256)):
                    if key == 'up':
                        tb.nudge_v(-1)
                    elif key == 'down':
                        tb.nudge_v(1)
                    elif key == 'left':
                        tb.nudge_h(-1)
                    elif key == 'right':
                        tb.nudge_h(1)
                    elif key in ('r', 'R'):
                        tb.reset_sync()
                    elif key in ('q', 'Q', '\x03'):
                        return
            v, h = tb.sync_status()
            rms = tb.update_agc()
            try:
                errlog.seek(0)
                ovf = errlog.read().count(b'sO')
            except OSError:
                ovf = 0
            lna, vga = tb.agc_gains()
            agc = "   rf:%+.0fdBFS%s lna:%d vga:%d" % (
                rms, " agc" if tb.agc else "", lna, vga)
            sys.stdout.write(
                "\r[sync] V:%+4d lines  H:%+4d px   lock:%3d%%   ovf:%d%s\x1b[K" %
                (v, h, tb.lock_pct(), ovf, agc))
            sys.stdout.flush()
    finally:
        sys.stderr.flush()
        os.dup2(saved_err, 2)
        os.close(saved_err)
        errlog.close()
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write("\n")
        sys.stdout.flush()


def main():
    ap = argparse.ArgumentParser(description="Gated FPV video viewer (one channel)")
    ap.add_argument('--sdr', default='uhd')
    ap.add_argument('--samp-rate', type=float, default=20e6)
    ap.add_argument('--gain', type=float, default=40.0)
    ap.add_argument('--lna', type=float, default=None,
                    help='hackrf LNA (IF) gain dB 0-40 (default 24)')
    ap.add_argument('--vga', type=float, default=None,
                    help='hackrf VGA (baseband) gain dB 0-62 (default 20)')
    ap.add_argument('--amp', action='store_true',
                    help='hackrf +14 dB front-end amp (OFF by default)')
    ap.add_argument('--dev-args', default='')
    ap.add_argument('--antenna', default=None)
    ap.add_argument('--freq', type=float, required=True)
    ap.add_argument('--frame-out', default='/tmp/fpv_frame.png',
                    help='where to write decoded frames when SDL is unavailable (macOS)')
    ap.add_argument('--no-window', action='store_true',
                    help='headless: decode to --frame-out only, no live window')
    ap.add_argument('--record', default=None,
                    help='record decoded video to this file (e.g. /tmp/fpv.mp4) via ffmpeg')
    ap.add_argument('--no-dcblock', action='store_true',
                    help='disable the zero-IF DC blocker on the decode path')
    ap.add_argument('--rotate', type=int, default=0, choices=[0, 90, 180, 270],
                    help='rotate the displayed video by this many degrees')
    ap.add_argument('--oversample', type=int, default=1,
                    help='capture at oversample*samp-rate then decimate (wide demod, correct decoder timing)')
    ap.add_argument('--contrast', type=float, default=1.35,
                    help='scale the demodulated composite onto the decoder black/white window')
    ap.add_argument('--video-offset', type=float, default=None,
                    help='DC shift applied after --contrast; derived from --sync-mid when unset')
    ap.add_argument('--sync-mid', type=float, default=SYNC_MID,
                    help='demodulated level midway between back porch and sync tip at '
                         'contrast 1.0; the offset keeps the decoder threshold there')
    ap.add_argument('--video-bw', type=float, default=1.25e6,
                    help='baseband low-pass cutoff feeding the decoder; gr-ntsc-rc documents '
                         '1.25 MHz, wider passes more detail and more sync-edge noise')
    ap.add_argument('--standard', choices=('ntsc', 'pal'), default='ntsc',
                    help='analog video standard: ntsc (525/60, 360x240, default) or '
                         'pal (625/50, 360x288 — common on EU FPV cameras)')
    ap.add_argument('--display', default=os.environ.get('FPV_DISPLAY', 'auto'),
                    choices=('auto', 'sdl', 'sdl-hw', 'ffplay'),
                    help='live video backend: auto/sdl = gr-video-sdl with a software YUV '
                         'overlay, sdl-hw = SDL hardware (Xv) overlay, ffplay = pipe raw '
                         'frames to ffplay (use when the SDL window stays blank)')
    ap.add_argument('--agc', action='store_true',
                    help='track RX gain to hold the ADC level at --agc-target; the HackRF has '
                         'no hardware AGC, this steps LNA (8 dB) and VGA (2 dB) in software')
    ap.add_argument('--agc-target', type=float, default=-20.0,
                    help='RMS level in dBFS the AGC aims for')
    ap.add_argument('--agc-lna-max', type=float, default=32.0,
                    help='ceiling on LNA so the AGC adds level with VGA instead of driving '
                         'the RF front end into compression')
    ap.add_argument('--if-offset', type=float, default=0.0,
                    help='tune this far off the channel and mix back in software, so the '
                         "zero-IF DC spike and the DC blocker's notch land beside the "
                         'carrier instead of on it (e.g. 3e6); 0 disables')
    ap.add_argument('--no-keys', action='store_true',
                    help='disable the interactive arrow-key vertical/horizontal sync tuner')
    args = ap.parse_args()

    if not HAVE_NTSC:
        sys.stderr.write(
            "[viewer] gnuradio.NTSC not built — the viewer needs the gr-ntsc-rc decoder.\n"
            "         Build the bundled copy:  ./setup.sh   (it builds vendor/gr-ntsc-rc)\n"
            "         It is not part of the DragonOS SDR stack; setup.sh builds it from vendor/.\n")
        sys.exit(2)

    tb = viewer(args.sdr, args.samp_rate, args.freq, args.gain,
                args.dev_args, args.antenna, frame_out=args.frame_out,
                record_path=args.record, live=(not args.no_window),
                dcblock=(not args.no_dcblock), rotate=args.rotate,
                oversample=args.oversample, contrast=args.contrast,
                lna=args.lna, vga=args.vga, amp=args.amp,
                standard=args.standard, display=args.display,
                video_offset=args.video_offset, video_bw=args.video_bw,
                sync_mid=args.sync_mid, agc=args.agc, agc_target=args.agc_target,
                agc_lna_max=args.agc_lna_max, if_offset=args.if_offset)

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()
    try:
        if not args.no_keys and keys_available():
            run_sync_tuner(tb)
        else:
            while not tb.window_closed():
                time.sleep(0.2)
                tb.update_agc()
    except (EOFError, KeyboardInterrupt):
        pass

    tb.stop()
    tb.wait()


if __name__ == '__main__':
    main()
