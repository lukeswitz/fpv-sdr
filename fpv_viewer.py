#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0

import sys
import time
import signal
import argparse

from gnuradio import gr, analog, filter
from gnuradio.filter import firdes
from gnuradio.fft import window
from gnuradio import video_sdl
import gnuradio.NTSC as NTSC

from fpv_sdr import build_source, quad_demod_gain


class viewer(gr.top_block):
    def __init__(self, sdr, samp_rate, freq, gain, dev_args, antenna):
        gr.top_block.__init__(self, "FPV Viewer", catch_exceptions=True)
        self.samp_rate = samp_rate
        self.frequency_carrier = freq

        self.src, self._retune = build_source(
            samp_rate, freq, gain, sdr=sdr, dev_args=dev_args, antenna=antenna)

        self.video_sdl_sink_0 = video_sdl.sink_s(0, 360, 240, (360 * 2), (240 * 2))
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
        self.connect((self.analog_quadrature_demod_cf_0, 0), (self.low_pass_filter_1, 0))
        self.connect((self.low_pass_filter_1, 0), (self.NTSC_decoder_c_0, 0))
        self.connect((self.src, 0), (self.analog_quadrature_demod_cf_0, 0))

    def retune(self, freq):
        self.frequency_carrier = freq
        self._retune(freq)


def main():
    ap = argparse.ArgumentParser(description="Gated FPV video viewer (one channel)")
    ap.add_argument('--sdr', default='uhd')
    ap.add_argument('--samp-rate', type=float, default=10e6)
    ap.add_argument('--gain', type=float, default=40.0)
    ap.add_argument('--dev-args', default='')
    ap.add_argument('--antenna', default=None)
    ap.add_argument('--freq', type=float, required=True)
    args = ap.parse_args()

    tb = viewer(args.sdr, args.samp_rate, args.freq, args.gain,
                args.dev_args, args.antenna)

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()
    try:
        while True:
            time.sleep(1)
    except (EOFError, KeyboardInterrupt):
        pass

    tb.stop()
    tb.wait()


if __name__ == '__main__':
    main()
