#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0

import math

UHD_ALIASES = ('uhd', 'antsdr', 'usrp', 'b210', 'b200', 'b200mini', 'pluto')


def _build_uhd(samp_rate, center_freq, gain, dev_args, antenna):
    from gnuradio import uhd

    src = uhd.usrp_source(
        dev_args,
        uhd.stream_args(cpu_format="fc32", args='', channels=[0]),
    )
    src.set_samp_rate(samp_rate)
    src.set_center_freq(center_freq, 0)
    src.set_antenna(antenna if antenna else 'TX/RX', 0)
    src.set_gain(gain, 0)

    def retune(freq):
        src.set_center_freq(freq, 0)

    return src, retune


def _build_soapy(driver, samp_rate, center_freq, gain, dev_args, antenna):
    try:
        from gnuradio import soapy
    except ImportError:
        raise SystemExit(
            "gr-soapy not installed (need it for --sdr %s). "
            "Install gnuradio soapy + the Soapy%s plugin." % (driver, driver)
        )

    dev = 'driver=%s' % driver
    src = soapy.source(dev, "fc32", 1, dev_args, '', [''], [''])
    src.set_sample_rate(0, samp_rate)
    src.set_frequency(0, center_freq)
    src.set_gain_mode(0, False)
    src.set_gain(0, float(gain))
    if antenna:
        src.set_antenna(0, antenna)

    def retune(freq):
        src.set_frequency(0, freq)

    return src, retune


def build_source(samp_rate, center_freq, gain, sdr='uhd', dev_args='', antenna=None):
    sdr = (sdr or 'uhd').lower()
    if sdr in UHD_ALIASES:
        return _build_uhd(samp_rate, center_freq, gain, dev_args, antenna)
    return _build_soapy(sdr, samp_rate, center_freq, gain, dev_args, antenna)


def quad_demod_gain(samp_rate):
    return samp_rate / (2 * math.pi * 850000000 / 8.0)
