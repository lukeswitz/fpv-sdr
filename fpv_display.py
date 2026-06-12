#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0

import os
import sys
import subprocess
import numpy as np
from gnuradio import gr
from PIL import Image


class frame_sink(gr.sync_block):
    def __init__(self, width=360, height=240, out_path=None, every=15,
                 record_path=None, record_fps=30, live=False, title='Dragon FPV'):
        gr.sync_block.__init__(self, name='fpv_frame_sink',
                               in_sig=[np.int16], out_sig=[])
        self.w = int(width)
        self.h = int(height)
        self.n = self.w * self.h
        self.out_path = out_path
        self.every = max(1, int(every))
        self._frame = np.zeros(self.n, dtype=np.int16)
        self._fill = 0
        self.frame_count = 0
        self._latest = None
        self._pipes = []

        size = '%dx%d' % (self.w, self.h)
        if live:
            self._pipes.append(subprocess.Popen(
                ['ffplay', '-hide_banner', '-loglevel', 'error', '-autoexit',
                 '-f', 'rawvideo', '-pixel_format', 'gray', '-video_size', size,
                 '-framerate', '30', '-window_title', title,
                 '-x', str(self.w * 2), '-y', str(self.h * 2), '-i', '-'],
                stdin=subprocess.PIPE))
            sys.stderr.write("[fpv] live window (ffplay)\n")
        if record_path:
            self._pipes.append(subprocess.Popen(
                ['ffmpeg', '-y', '-loglevel', 'error',
                 '-f', 'rawvideo', '-pix_fmt', 'gray', '-s', size,
                 '-r', str(record_fps), '-i', '-', '-pix_fmt', 'yuv420p', record_path],
                stdin=subprocess.PIPE))
            sys.stderr.write("[fpv] recording to %s\n" % record_path)

    def get_latest(self):
        return self._latest

    def stop(self):
        pipes = self._pipes
        self._pipes = []
        for p in pipes:
            if p.stdin is not None:
                p.stdin.close()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        return True

    def _on_frame(self):
        img = np.clip(self._frame, 0, 255).astype(np.uint8).reshape(self.h, self.w)
        self._latest = img
        if self._pipes:
            data = img.tobytes()
            alive = []
            for p in self._pipes:
                try:
                    p.stdin.write(data)
                except (BrokenPipeError, ValueError):
                    continue
                alive.append(p)
            self._pipes = alive
        self.frame_count += 1
        if self.out_path and self.frame_count % self.every == 0:
            tmp = self.out_path + '.tmp'
            try:
                Image.fromarray(img, mode='L').save(tmp, format='PNG')
                os.replace(tmp, self.out_path)
            except OSError:
                pass

    def work(self, input_items, output_items):
        x = input_items[0]
        total = len(x)
        i = 0
        while i < total:
            take = min(self.n - self._fill, total - i)
            self._frame[self._fill:self._fill + take] = x[i:i + take]
            self._fill += take
            i += take
            if self._fill >= self.n:
                self._on_frame()
                self._fill = 0
        return total


class decoder_sink(gr.sync_block):
    def __init__(self, width=360, height=240, out_path=None, every=15,
                 record_path=None, record_fps=30, live=False, title='Dragon FPV'):
        gr.sync_block.__init__(self, name='fpv_decoder_sink',
                               in_sig=[np.float32, np.float32, np.float32], out_sig=[])
        self.w = int(width)
        self.h = int(height)
        self.n = self.w * self.h
        self.out_path = out_path
        self.every = max(1, int(every))
        self._frame = np.full((self.h, self.w), 16, dtype=np.uint8)
        self._valid = 0
        self.frame_count = 0
        self._pipes = []

        size = '%dx%d' % (self.w, self.h)
        if live:
            self._pipes.append(subprocess.Popen(
                ['ffplay', '-hide_banner', '-loglevel', 'error', '-autoexit',
                 '-f', 'rawvideo', '-pixel_format', 'gray', '-video_size', size,
                 '-framerate', '30', '-window_title', title,
                 '-x', str(self.w * 2), '-y', str(self.h * 2), '-i', '-'],
                stdin=subprocess.PIPE))
            sys.stderr.write("[fpv] live window (ffplay)\n")
        if record_path:
            self._pipes.append(subprocess.Popen(
                ['ffmpeg', '-y', '-loglevel', 'error',
                 '-f', 'rawvideo', '-pix_fmt', 'gray', '-s', size,
                 '-r', str(record_fps), '-i', '-', '-pix_fmt', 'yuv420p', record_path],
                stdin=subprocess.PIPE))
            sys.stderr.write("[fpv] recording to %s\n" % record_path)

    def stop(self):
        pipes = self._pipes
        self._pipes = []
        for p in pipes:
            if p.stdin is not None:
                p.stdin.close()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        return True

    def _emit(self):
        img = self._frame
        if self._pipes:
            data = img.tobytes()
            alive = []
            for p in self._pipes:
                try:
                    p.stdin.write(data)
                except (BrokenPipeError, ValueError):
                    continue
                alive.append(p)
            self._pipes = alive
        self.frame_count += 1
        if self.out_path and self.frame_count % self.every == 0:
            tmp = self.out_path + '.tmp'
            try:
                Image.fromarray(img, mode='L').save(tmp, format='PNG')
                os.replace(tmp, self.out_path)
            except OSError:
                pass

    def work(self, input_items, output_items):
        xi = input_items[0].astype(np.int32)
        yi = input_items[1].astype(np.int32)
        lm = input_items[2]
        valid = (xi >= 0) & (xi < self.w) & (yi >= 0) & (yi < self.h) & (lm >= 0)
        v = int(np.count_nonzero(valid))
        if v:
            idx = yi[valid] * self.w + xi[valid]
            self._frame.reshape(-1)[idx] = np.clip(lm[valid], 0, 255).astype(np.uint8)
            self._valid += v
            while self._valid >= self.n:
                self._valid -= self.n
                self._emit()
        return len(input_items[0])
