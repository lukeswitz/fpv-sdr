#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0

import os
import sys
import time
import signal
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gnuradio import gr, analog, filter
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
                 frame_out='/tmp/fpv_frame.png', record_path=None):
        gr.top_block.__init__(self, "FPV Viewer", catch_exceptions=True)
        self.samp_rate = samp_rate
        self.frequency_carrier = freq

        self.src, self._retune = build_source(
            samp_rate, freq, gain, sdr=sdr, dev_args=dev_args, antenna=antenna)

        self.recorder = None
        if HAVE_SDL:
            self.video_sdl_sink_0 = video_sdl.sink_s(0, 360, 240, (360 * 2), (240 * 2))
            if record_path:
                self.recorder = frame_sink(360, 240, None, record_path=record_path)
        else:
            self.video_sdl_sink_0 = frame_sink(360, 240, frame_out, record_path=record_path)
        self.low_pass_filter_1 = filter.fir_filter_fff(
            1,
            firdes.low_pass(1, samp_rate, 2e6, 2e6, window.WIN_HAMMING, 6.76))
        self.analog_quadrature_demod_cf_0 = analog.quadrature_demod_cf(
            quad_demod_gain(samp_rate))
        self.NTSC_video_stream_converter_c_0 = NTSC.video_stream_converter_c(
            samp_rate, samp_rate / (360 * 240 * 60))
        self.NTSC_decoder_c_0 = NTSC.decoder_c(samp_rate)

        self.connect((self.NTSC_decoder_c_0, 2), (self.NTSC_video_stream_converter_c_0, 2))
        self.connect((self.NTSC_decoder_c_0, 3), (self.NTSC_video_stream_converter_c_0, 3))
        self.connect((self.NTSC_decoder_c_0, 0), (self.NTSC_video_stream_converter_c_0, 0))
        self.connect((self.NTSC_decoder_c_0, 1), (self.NTSC_video_stream_converter_c_0, 1))
        self.connect((self.NTSC_video_stream_converter_c_0, 0), (self.video_sdl_sink_0, 0))
        if self.recorder is not None:
            self.connect((self.NTSC_video_stream_converter_c_0, 0), (self.recorder, 0))
        self.connect((self.analog_quadrature_demod_cf_0, 0), (self.low_pass_filter_1, 0))
        self.connect((self.low_pass_filter_1, 0), (self.NTSC_decoder_c_0, 0))
        if sdr.lower() in UHD_ALIASES:
            self.connect((self.src, 0), (self.analog_quadrature_demod_cf_0, 0))
        else:
            self.dcblock = filter.dc_blocker_cc(32, True)
            self.connect((self.src, 0), self.dcblock)
            self.connect(self.dcblock, (self.analog_quadrature_demod_cf_0, 0))

    def retune(self, freq):
        self.frequency_carrier = freq
        self._retune(freq)


def run_live(tb, sink):
    if sys.platform == 'darwin':
        os.environ.setdefault('MPLBACKEND', 'macosx')
    import matplotlib.pyplot as plt
    import numpy as np

    plt.ion()
    fig, ax = plt.subplots(figsize=(6, 4))
    fig.canvas.manager.set_window_title('Dragon FPV')
    ax.set_title('%.0f MHz' % (tb.frequency_carrier / 1e6))
    ax.axis('off')
    im = ax.imshow(np.zeros((sink.h, sink.w), dtype=np.uint8),
                   cmap='gray', vmin=0, vmax=255)
    while plt.fignum_exists(fig.number):
        frame = sink.get_latest()
        if frame is not None:
            im.set_data(frame)
            fig.canvas.draw_idle()
        plt.pause(0.03)


def main():
    ap = argparse.ArgumentParser(description="Gated FPV video viewer (one channel)")
    ap.add_argument('--sdr', default='uhd')
    ap.add_argument('--samp-rate', type=float, default=10e6)
    ap.add_argument('--gain', type=float, default=40.0)
    ap.add_argument('--dev-args', default='')
    ap.add_argument('--antenna', default=None)
    ap.add_argument('--freq', type=float, required=True)
    ap.add_argument('--frame-out', default='/tmp/fpv_frame.png',
                    help='where to write decoded frames when SDL is unavailable (macOS)')
    ap.add_argument('--no-window', action='store_true',
                    help='headless: decode to --frame-out only, no live window')
    ap.add_argument('--record', default=None,
                    help='record decoded video to this file (e.g. /tmp/fpv.mp4) via ffmpeg')
    args = ap.parse_args()

    tb = viewer(args.sdr, args.samp_rate, args.freq, args.gain,
                args.dev_args, args.antenna, frame_out=args.frame_out,
                record_path=args.record)
    if not HAVE_SDL:
        sys.stderr.write("[fpv] video_sdl absent — writing frames to %s\n" % args.frame_out)

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()
    try:
        if not HAVE_SDL and not args.no_window:
            run_live(tb, tb.video_sdl_sink_0)
        else:
            while True:
                time.sleep(1)
    except (EOFError, KeyboardInterrupt):
        pass

    tb.stop()
    tb.wait()


if __name__ == '__main__':
    main()
