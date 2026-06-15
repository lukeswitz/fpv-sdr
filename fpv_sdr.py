#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0

import sys
import math

UHD_ALIASES = ('uhd', 'antsdr', 'usrp', 'b200', 'b210', 'b200mini')

SOAPY_DRIVERS = {'pluto': 'plutosdr'}


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


def _build_soapy(driver, samp_rate, center_freq, gain, dev_args, antenna, lna, vga, amp):
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
    src.set_bandwidth(0, min(28e6, samp_rate))
    src.set_gain_mode(0, False)

    if driver == 'hackrf':
        lna_db = max(0.0, min(40.0, float(gain if lna is None else lna)))
        vga_db = max(0.0, min(62.0, float(gain if vga is None else vga)))
        amp_db = 14.0 if amp else 0.0
        src.set_gain(0, 'AMP', amp_db)
        src.set_gain(0, 'LNA', lna_db)
        src.set_gain(0, 'VGA', vga_db)
        sys.stderr.write(
            "[fpv] hackrf RX gains: AMP=%g LNA=%g VGA=%g (max input -5 dBm; "
            "AMP off keeps the front-end safe)\n" % (amp_db, lna_db, vga_db))
    else:
        src.set_gain(0, float(gain))

    if antenna:
        src.set_antenna(0, antenna)

    def retune(freq):
        src.set_frequency(0, freq)

    return src, retune


def build_source(samp_rate, center_freq, gain, sdr='uhd', dev_args='', antenna=None,
                 lna=None, vga=None, amp=False):
    sdr = (sdr or 'uhd').lower()
    try:
        if sdr in UHD_ALIASES:
            return _build_uhd(samp_rate, center_freq, gain, dev_args, antenna)
        driver = SOAPY_DRIVERS.get(sdr, sdr)
        return _build_soapy(driver, samp_rate, center_freq, gain, dev_args, antenna, lna, vga, amp)
    except RuntimeError as e:
        raise SystemExit(
            "[fpv] no '%s' device found: %s\n"
            "      plugged in? check:  SoapySDRUtil --find   (or uhd_find_devices)" % (sdr, e))


def quad_demod_gain(samp_rate):
    return samp_rate / (2 * math.pi * 850000000 / 8.0)
