#!/usr/bin/env bash
set -o pipefail
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

case "${1:-}" in
    -h|--help) printf 'usage: %s [image ...]\n  fresh-install test in clean Debian/Ubuntu containers (default: ubuntu:24.04 ubuntu:22.04 debian:12)\n  runs ./setup.sh then ./tests/smoke_test.sh in each; host repo is mounted read-only\n' "$0"; exit 0 ;;
esac

if ! command -v docker >/dev/null 2>&1; then
    printf 'docker not found — install Docker Desktop (https://www.docker.com) and start it, then re-run.\n' >&2
    exit 1
fi
if ! docker info >/dev/null 2>&1; then
    printf 'docker is installed but not running — start Docker Desktop, then re-run.\n' >&2
    exit 1
fi

IMAGES=("$@")
[[ ${#IMAGES[@]} -eq 0 ]] && IMAGES=(ubuntu:24.04 ubuntu:22.04 debian:12)

RESULTS=()
fail=0
for img in "${IMAGES[@]}"; do
    printf '\n\033[1;36m==================== %s ====================\033[0m\n' "$img"
    if docker run --rm -e DEBIAN_FRONTEND=noninteractive -e TZ=Etc/UTC \
        -v "$PROJECT_DIR":/src:ro "$img" bash -c "
        set -e
        ln -snf /usr/share/zoneinfo/Etc/UTC /etc/localtime
        apt-get update -qq
        apt-get install -y -qq sudo rsync ca-certificates git >/dev/null
        rsync -a --exclude=.git --exclude=__pycache__ /src/ /work/
        cd /work
        ./setup.sh
        ./tests/smoke_test.sh
    "; then
        RESULTS+=("PASS  $img")
    else
        RESULTS+=("FAIL  $img")
        fail=1
    fi
done

printf '\n\033[1m==================== docker matrix ====================\033[0m\n'
for r in "${RESULTS[@]}"; do
    case "$r" in
        PASS*) printf '  \033[32m%s\033[0m\n' "$r" ;;
        *)     printf '  \033[31m%s\033[0m\n' "$r" ;;
    esac
done
exit "$fail"
