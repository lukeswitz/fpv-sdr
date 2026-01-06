#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Top Block
# GNU Radio version: 3.10.10.0

from gnuradio import analog
import math
from gnuradio import blocks
from gnuradio import filter
from gnuradio.filter import firdes
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import uhd
import time
from gnuradio import video_sdl
import gnuradio.NTSC as NTSC




class top_block(gr.top_block):

    def __init__(self):
        gr.top_block.__init__(self, "Top Block", catch_exceptions=True)

        ##################################################
        # Variables
        ##################################################
        self.samp_rate = samp_rate = 10e6
        self.frequency_carrier = frequency_carrier = 5725e6
        self.bandwidth = bandwidth = 5e6

        ##################################################
        # Blocks
        ##################################################

        self.video_sdl_sink_0 = video_sdl.sink_s(0, 360, 240, (360 * 2), (240 * 2))
        self.uhd_usrp_source_0 = uhd.usrp_source(
            ",".join(("", "")),
            uhd.stream_args(
                cpu_format="fc32",
                args='',
                channels=list(range(0,2)),
            ),
        )
        self.uhd_usrp_source_0.set_samp_rate(samp_rate)
        self.uhd_usrp_source_0.set_time_unknown_pps(uhd.time_spec(0))

        self.uhd_usrp_source_0.set_center_freq(frequency_carrier, 0)
        self.uhd_usrp_source_0.set_antenna('TX/RX', 0)
        self.uhd_usrp_source_0.set_gain(40, 0)

        self.uhd_usrp_source_0.set_center_freq(frequency_carrier, 1)
        self.uhd_usrp_source_0.set_antenna('TX/RX', 1)
        self.uhd_usrp_source_0.set_gain(0, 1)
        self.low_pass_filter_1 = filter.fir_filter_fff(
            1,
            firdes.low_pass(
                1,
                samp_rate,
                2e6,
                2e6,
                window.WIN_HAMMING,
                6.76))
        self.blocks_null_sink_0 = blocks.null_sink(gr.sizeof_gr_complex*1)
        self.analog_quadrature_demod_cf_0 = analog.quadrature_demod_cf((samp_rate/(2*math.pi*850000000/8.0)))
        self.NTSC_video_stream_converter_c_0 = NTSC.video_stream_converter_c(samp_rate, samp_rate / (360 * 240 * 60))
        self.NTSC_decoder_c_0 = NTSC.decoder_c(samp_rate)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.NTSC_decoder_c_0, 2), (self.NTSC_video_stream_converter_c_0, 2))
        self.connect((self.NTSC_decoder_c_0, 3), (self.NTSC_video_stream_converter_c_0, 3))
        self.connect((self.NTSC_decoder_c_0, 0), (self.NTSC_video_stream_converter_c_0, 0))
        self.connect((self.NTSC_decoder_c_0, 1), (self.NTSC_video_stream_converter_c_0, 1))
        self.connect((self.NTSC_video_stream_converter_c_0, 0), (self.video_sdl_sink_0, 0))
        self.connect((self.analog_quadrature_demod_cf_0, 0), (self.low_pass_filter_1, 0))
        self.connect((self.low_pass_filter_1, 0), (self.NTSC_decoder_c_0, 0))
        self.connect((self.uhd_usrp_source_0, 0), (self.analog_quadrature_demod_cf_0, 0))
        self.connect((self.uhd_usrp_source_0, 1), (self.blocks_null_sink_0, 0))


    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.analog_quadrature_demod_cf_0.set_gain((self.samp_rate/(2*math.pi*850000000/8.0)))
        self.low_pass_filter_1.set_taps(firdes.low_pass(1, self.samp_rate, 2e6, 2e6, window.WIN_HAMMING, 6.76))
        self.uhd_usrp_source_0.set_samp_rate(self.samp_rate)

    def get_frequency_carrier(self):
        return self.frequency_carrier

    def set_frequency_carrier(self, frequency_carrier):
        self.frequency_carrier = frequency_carrier
        self.uhd_usrp_source_0.set_center_freq(self.frequency_carrier, 0)
        self.uhd_usrp_source_0.set_center_freq(self.frequency_carrier, 1)

    def get_bandwidth(self):
        return self.bandwidth

    def set_bandwidth(self, bandwidth):
        self.bandwidth = bandwidth




def main(top_block_cls=top_block, options=None):
    tb = top_block_cls()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()

    try:
        time.sleep(999999)
    except EOFError:
        pass
    tb.stop()
    tb.wait()


if __name__ == '__main__':
    main()
