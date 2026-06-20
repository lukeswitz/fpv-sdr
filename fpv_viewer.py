#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0

import os
import sys
import time
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


class viewer(gr.top_block):
    def __init__(self, sdr, samp_rate, freq, gain, dev_args, antenna,
                 frame_out='/tmp/fpv_frame.png', record_path=None, live=True, dcblock=True,
                 rotate=0, oversample=2, contrast=1.0, lna=None, vga=None, amp=False,
                 standard='ntsc'):
        gr.top_block.__init__(self, "FPV Viewer", catch_exceptions=True)
        self.samp_rate = samp_rate
        self.frequency_carrier = freq

        is_pal = str(standard).lower() == 'pal'
        self.vid_w, self.vid_h, field_rate, std_code = (
            (360, 288, 50, 1) if is_pal else (360, 240, 60, 0))

        oversample = max(1, int(oversample))
        self.cap_rate = cap_rate = samp_rate * oversample
        self.src, self._retune = build_source(
            cap_rate, freq, gain, sdr=sdr, dev_args=dev_args, antenna=antenna,
            lna=lna, vga=vga, amp=amp)

        title = 'FPV-SDR %.0f MHz' % (freq / 1e6)
        self.low_pass_filter_1 = filter.fir_filter_fff(
            oversample,
            firdes.low_pass(1, cap_rate, 2e6, 2e6, window.WIN_HAMMING, 6.76))
        self.analog_quadrature_demod_cf_0 = analog.quadrature_demod_cf(
            quad_demod_gain(cap_rate) * contrast)
        self.NTSC_decoder_c_0 = NTSC.decoder_c(samp_rate, std_code)

        if sdr.lower() in UHD_ALIASES or not dcblock:
            self.connect((self.src, 0), (self.analog_quadrature_demod_cf_0, 0))
        else:
            self.dcblock = filter.dc_blocker_cc(32, True)
            self.connect((self.src, 0), self.dcblock)
            self.connect(self.dcblock, (self.analog_quadrature_demod_cf_0, 0))
        self.connect((self.analog_quadrature_demod_cf_0, 0), (self.low_pass_filter_1, 0))
        self.connect((self.low_pass_filter_1, 0), (self.NTSC_decoder_c_0, 0))

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

        lock_win = max(1, int(samp_rate * 0.02))
        self.lock_state = blocks.add_const_ff(-1.0)
        self.lock_abs = blocks.abs_ff(1)
        self.lock_avg = blocks.moving_average_ff(lock_win, 1.0 / lock_win, 4000, 1)
        self.lock_probe = blocks.probe_signal_f()
        self.connect((self.NTSC_decoder_c_0, 0), self.lock_state,
                     self.lock_abs, self.lock_avg, self.lock_probe)

        self.recorder = None
        self.frame_sink_0 = None
        if HAVE_SDL:
            self.video_sdl_sink_0 = video_sdl.sink_s(
                0, self.vid_w, self.vid_h, (self.vid_w * 2), (self.vid_h * 2))
            self.connect((self.sync_delay, 0), (self.video_sdl_sink_0, 0))
            if record_path:
                self.recorder = frame_sink(self.vid_w, self.vid_h, None, record_path=record_path, rotate=rotate)
                self.connect((self.sync_delay, 0), (self.recorder, 0))
        else:
            self.frame_sink_0 = frame_sink(
                self.vid_w, self.vid_h, frame_out, record_path=record_path, live=live, title=title,
                rotate=rotate)
            self.connect((self.sync_delay, 0), (self.frame_sink_0, 0))

    def retune(self, freq):
        self.frequency_carrier = freq
        self._retune(freq)

    def set_contrast(self, contrast):
        self.analog_quadrature_demod_cf_0.set_gain(quad_demod_gain(self.cap_rate) * contrast)

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

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
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
            sys.stdout.write(
                "\r[sync] V:%+4d lines  H:%+4d px   lock:%3d%%\x1b[K" %
                (v, h, tb.lock_pct()))
            sys.stdout.flush()
    finally:
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
    ap.add_argument('--contrast', type=float, default=1.0,
                    help='multiply the quad-demod gain to match the decoder sync/black/white levels')
    ap.add_argument('--standard', choices=('ntsc', 'pal'), default='ntsc',
                    help='analog video standard: ntsc (525/60, 360x240, default) or '
                         'pal (625/50, 360x288 — common on EU FPV cameras)')
    ap.add_argument('--no-keys', action='store_true',
                    help='disable the interactive arrow-key vertical/horizontal sync tuner')
    args = ap.parse_args()

    if not HAVE_NTSC:
        sys.stderr.write(
            "[viewer] gnuradio.NTSC not built — the viewer needs the gr-ntsc-rc decoder.\n"
            "         Build the bundled copy:  ./setup.sh   (it builds vendor/gr-ntsc-rc)\n"
            "         DragonOS ships it prebuilt; see the README 'Install' section.\n")
        sys.exit(2)

    tb = viewer(args.sdr, args.samp_rate, args.freq, args.gain,
                args.dev_args, args.antenna, frame_out=args.frame_out,
                record_path=args.record, live=(not args.no_window),
                dcblock=(not args.no_dcblock), rotate=args.rotate,
                oversample=args.oversample, contrast=args.contrast,
                lna=args.lna, vga=args.vga, amp=args.amp,
                standard=args.standard)

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
    except (EOFError, KeyboardInterrupt):
        pass

    tb.stop()
    tb.wait()


if __name__ == '__main__':
    main()
