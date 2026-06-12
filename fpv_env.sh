#!/usr/bin/env bash

resolve_fpv_python() {
    if [[ -n "$FPV_PYTHON" ]]; then
        PYTHON="$FPV_PYTHON"
        return 0
    fi

    if command -v python3 >/dev/null 2>&1 && python3 -c "import gnuradio.gr" >/dev/null 2>&1; then
        PYTHON="python3"
        return 0
    fi

    local grdir grver cand np
    for grdir in /opt/homebrew/lib/python3.*/site-packages/gnuradio /usr/local/lib/python3.*/site-packages/gnuradio; do
        [[ -d "$grdir" ]] || continue
        grver=$(printf '%s\n' "$grdir" | sed -E 's#.*/(python3\.[0-9]+)/.*#\1#')
        for cand in \
            "/opt/homebrew/opt/${grver/python/python@}/bin/${grver}" \
            "/opt/homebrew/bin/${grver}" \
            "/usr/local/opt/${grver/python/python@}/bin/${grver}" \
            "/usr/local/bin/${grver}"; do
            [[ -x "$cand" ]] || continue
            if ! "$cand" -c "import numpy" >/dev/null 2>&1; then
                for np in "/opt/homebrew/opt/numpy/lib/${grver}/site-packages" \
                          "/usr/local/opt/numpy/lib/${grver}/site-packages"; do
                    if [[ -d "$np" ]]; then
                        export PYTHONPATH="${np}${PYTHONPATH:+:$PYTHONPATH}"
                        break
                    fi
                done
            fi
            local oot="${HOME}/.local/lib/${grver}/site-packages"
            [[ -d "$oot" ]] && export PYTHONPATH="${oot}${PYTHONPATH:+:$PYTHONPATH}"
            if "$cand" -c "import gnuradio.gr" >/dev/null 2>&1; then
                PYTHON="$cand"
                return 0
            fi
        done
    done

    echo "[ERROR] No Python with GNU Radio bindings found. Set FPV_PYTHON=/path/to/python3" >&2
    return 1
}
