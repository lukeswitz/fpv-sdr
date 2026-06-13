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
import gnuradio.NTSC as NTSC

try:
    from gnuradio import video_sdl
    HAVE_SDL = True
except Exception:
    video_sdl = None
    HAVE_SDL = False

from fpv_sdr import build_source, quad_demod_gain, UHD_ALIASES
from fpv_display import frame_sink


class viewer(gr.top_block):
    def __init__(self, sdr, samp_rate, freq, gain, dev_args, antenna,
                 frame_out='/tmp/fpv_frame.png', record_path=None, live=True, dcblock=True,
                 rotate=0, oversample=2, contrast=1.0, lna=None, vga=None, amp=False):
        gr.top_block.__init__(self, "FPV Viewer", catch_exceptions=True)
        self.samp_rate = samp_rate
        self.frequency_carrier = freq

        oversample = max(1, int(oversample))
        self.cap_rate = cap_rate = samp_rate * oversample
        self.src, self._retune = build_source(
            cap_rate, freq, gain, sdr=sdr, dev_args=dev_args, antenna=antenna,
            lna=lna, vga=vga, amp=amp)

        title = 'Dragon FPV %.0f MHz' % (freq / 1e6)
        self.low_pass_filter_1 = filter.fir_filter_fff(
            oversample,
            firdes.low_pass(1, cap_rate, 2e6, 2e6, window.WIN_HAMMING, 6.76))
        self.analog_quadrature_demod_cf_0 = analog.quadrature_demod_cf(
            quad_demod_gain(cap_rate) * contrast)
        self.NTSC_decoder_c_0 = NTSC.decoder_c(samp_rate)

        if sdr.lower() in UHD_ALIASES or not dcblock:
            self.connect((self.src, 0), (self.analog_quadrature_demod_cf_0, 0))
        else:
            self.dcblock = filter.dc_blocker_cc(32, True)
            self.connect((self.src, 0), self.dcblock)
            self.connect(self.dcblock, (self.analog_quadrature_demod_cf_0, 0))
        self.connect((self.analog_quadrature_demod_cf_0, 0), (self.low_pass_filter_1, 0))
        self.connect((self.low_pass_filter_1, 0), (self.NTSC_decoder_c_0, 0))

        self.NTSC_video_stream_converter_c_0 = NTSC.video_stream_converter_c(
            samp_rate, samp_rate / (360 * 240 * 60))
        self.connect((self.NTSC_decoder_c_0, 0), (self.NTSC_video_stream_converter_c_0, 0))
        self.connect((self.NTSC_decoder_c_0, 1), (self.NTSC_video_stream_converter_c_0, 1))
        self.connect((self.NTSC_decoder_c_0, 2), (self.NTSC_video_stream_converter_c_0, 2))
        self.connect((self.NTSC_decoder_c_0, 3), (self.NTSC_video_stream_converter_c_0, 3))

        self.recorder = None
        self.frame_sink_0 = None
        if HAVE_SDL:
            self.video_sdl_sink_0 = video_sdl.sink_s(0, 360, 240, (360 * 2), (240 * 2))
            self.connect((self.NTSC_video_stream_converter_c_0, 0), (self.video_sdl_sink_0, 0))
            if record_path:
                self.recorder = frame_sink(360, 240, None, record_path=record_path, rotate=rotate)
                self.connect((self.NTSC_video_stream_converter_c_0, 0), (self.recorder, 0))
        else:
            self.frame_sink_0 = frame_sink(
                360, 240, frame_out, record_path=record_path, live=live, title=title,
                rotate=rotate)
            self.connect((self.NTSC_video_stream_converter_c_0, 0), (self.frame_sink_0, 0))

    def retune(self, freq):
        self.frequency_carrier = freq
        self._retune(freq)

    def set_contrast(self, contrast):
        self.analog_quadrature_demod_cf_0.set_gain(quad_demod_gain(self.cap_rate) * contrast)

    def window_closed(self):
        return self.frame_sink_0 is not None and self.frame_sink_0.closed


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
    args = ap.parse_args()

    tb = viewer(args.sdr, args.samp_rate, args.freq, args.gain,
                args.dev_args, args.antenna, frame_out=args.frame_out,
                record_path=args.record, live=(not args.no_window),
                dcblock=(not args.no_dcblock), rotate=args.rotate,
                oversample=args.oversample, contrast=args.contrast,
                lna=args.lna, vga=args.vga, amp=args.amp)

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()
    try:
        while not tb.window_closed():
            time.sleep(0.2)
    except (EOFError, KeyboardInterrupt):
        pass

    tb.stop()
    tb.wait()


if __name__ == '__main__':
    main()
