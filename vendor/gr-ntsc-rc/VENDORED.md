# Vendored gr-ntsc-rc

This is a frozen, build-ready copy of the gr-ntsc-rc NTSC decoder. It removes two
moving dependencies from the build: a GitHub PR head that can be rebased/closed, and a
patch applied at build time that could fail to apply.

| | |
|---|---|
| Upstream | https://github.com/lscardoso/gr-ntsc-rc |
| Pinned commit | `b8c54ea2f66f0e6eb604a1a749d0e653f0b0cfca` ("Bump to 3.10/3.11") |
| Source branch | PR #6 (`pull/6/head`) — GNU Radio 3.10 / 3.11 support |
| Applied on top | `patches/gr-ntsc-rc-converter-bounds.patch` (already baked in) |
| Applied on top | `patches/gr-ntsc-rc-pal-support.patch` (already baked in) |
| License | GPLv3 (see `LICENSE` in this directory) |

The converter-bounds fix repairs an out-of-bounds read in
`lib/video_stream_converter_c_impl.cc` — the loop read `decimation * noutput_items`
samples from an `noutput_items` buffer, which segfaulted on marginal signals. The fix
clamps the read to the real input length (`ninput = noutput_items * decimation()`).

The PAL-support patch adds runtime NTSC/PAL selection. `decoder_c::make` gains a
`standard` arg (0=NTSC default, 1=PAL) selecting line/porch durations and active-line
geometry; `video_stream_converter_c::make` gains `width`/`height` and its image matrix
is sized to the PAL maximum (`MAX_Y_HEIGHT`). The decoder is luma-only, so PAL needs
only timing/geometry — no chroma path. NTSC behavior is byte-identical (default args,
NTSC values sourced from the original `#define`s). Validated by `tests/test_pal_decode.py`.

`setup.sh` builds this tree directly. Nothing here is fetched at build time.

## Re-syncing with upstream
```bash
git clone https://github.com/lscardoso/gr-ntsc-rc.git /tmp/ntsc
cd /tmp/ntsc
git fetch origin pull/6/head:pr6 && git checkout pr6
git apply /path/to/dragon-fpv-decoder/patches/gr-ntsc-rc-converter-bounds.patch
git apply /path/to/dragon-fpv-decoder/patches/gr-ntsc-rc-pal-support.patch
rsync -a --exclude='.git' --exclude='build' ./ /path/to/dragon-fpv-decoder/vendor/gr-ntsc-rc/
# then update the pinned commit above
```
