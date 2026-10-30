#!/usr/bin/env bash
# check.sh - static checks that need no kernel build and no QEMU.
#
# Runtime boot and installer coverage lives in build/test-boot.sh and
# build/test-install.sh; this script is the fast gate every change must pass.

set -Eeuo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

cd "$GRINTION_REPO_ROOT"
FAILED=0

fail() { printf '\033[1;31m[FAIL]\033[0m %s\n' "$*" >&2; FAILED=1; }
pass() { printf '\033[1;32m[ ok ]\033[0m %s\n' "$*"; }

# Our shell scripts only. build/work holds the kernel source tree and must
# never be scanned: it contains upstream scripts for other shells.
SHELL_FILES=()
while IFS= read -r -d '' script; do
    IFS= read -r first_line < "$script" || true
    case "$first_line" in
        '#!'*'/sh'*|'#!'*'/bash'*|'#!'*' sh'*|'#!'*' bash'*)
            SHELL_FILES+=("$script") ;;
    esac
done < <(find bin build init etc \
              \( -path 'build/work' -o -path 'build/cache' \) -prune -o \
              -type f -print0)

log "checking shell syntax"
if [ "${#SHELL_FILES[@]}" -eq 0 ]; then
    fail "no shell scripts found"
else
    for script in "${SHELL_FILES[@]}"; do
        bash -n "$script" || fail "syntax error: $script"
    done
fi
pass "shell syntax"

if command -v shellcheck >/dev/null 2>&1; then
    log "running shellcheck"
    if ! shellcheck --severity=warning "${SHELL_FILES[@]}"; then
        fail "shellcheck reported problems"
    else
        pass "shellcheck"
    fi
else
    warn "shellcheck is not installed; skipping lint (install shellcheck to enable)"
fi

log "checking Python sources"
PY_FILES=("bin/garb")
while IFS= read -r -d '' path; do
    PY_FILES+=("$path")
done < <(find build tests -maxdepth 1 -type f -name '*.py' -print0)
if python3 -m py_compile "${PY_FILES[@]}"; then
    pass "Python compilation"
else
    fail "Python compilation failed"
fi

log "checking executable bits"
for path in bin/* init/* build/*.sh build/*.py etc/runit/* etc/sv/*/run; do
    [ -f "$path" ] || continue
    [ -x "$path" ] || fail "not executable: $path"
done
pass "executable bits"

# A stale rootfs from an older build can mask a missing dlopen plugin. Check
# it when it exists; the rootfs build itself also enforces this.
if [ -d build/work/rootfs ]; then
    [ -f build/work/rootfs/usr/lib/sudo/sudoers.so ] \
        || fail "sudoers.so missing from build/work/rootfs"
    [ -x build/work/rootfs/usr/bin/grintion-doctor ] \
        || fail "grintion-doctor missing from build/work/rootfs"
fi
pass "runtime components in staged rootfs"

log "checking host build inputs"
while IFS= read -r cmd; do
    [ -n "$cmd" ] || continue
    case "$cmd" in \#*) continue ;; esac
    [ "$cmd" = sh ] && continue
    type -P "$cmd" >/dev/null 2>&1 || fail "required host command missing: $cmd"
done < config/rootfs.required-binaries
pass "host build inputs"

log "checking documentation links"
python3 - <<'PY' || fail "documentation link check failed"
from pathlib import Path
import re, sys

root = Path(".").resolve()
bad = []
for doc in list(root.glob("*.md")) + list((root / "docs").glob("*.md")):
    text = doc.read_text(encoding="utf-8")
    for target in re.findall(r"\[[^\]]*\]\(([^)#]+)(?:#[^)]*)?\)", text):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        path = (doc.parent / target).resolve()
        if not path.exists():
            bad.append(f"{doc.relative_to(root)} -> {target}")
for item in bad:
    print(f"broken link: {item}", file=sys.stderr)
sys.exit(1 if bad else 0)
PY
pass "documentation links"

log "checking for accidental home-directory paths"
if grep -rnI --exclude-dir=.git --exclude-dir=.venv --exclude-dir=build \
        --exclude-dir=output --exclude-dir=tools \
        -E '/home/[A-Za-z0-9._-]+/' . >/tmp/grintion-home-paths 2>/dev/null; then
    cat /tmp/grintion-home-paths >&2
    fail "absolute home-directory path found"
else
    pass "no absolute home paths"
fi

log "running garb unit and integration tests"
PYTHON_BIN="${PYTHON:-python3}"
PYTEST_READY=1
if ! "$PYTHON_BIN" -c 'import pytest' >/dev/null 2>&1; then
    if [ -x "$GRINTION_REPO_ROOT/.venv/bin/python3" ] \
        && "$GRINTION_REPO_ROOT/.venv/bin/python3" -c 'import pytest' >/dev/null 2>&1; then
        PYTHON_BIN="$GRINTION_REPO_ROOT/.venv/bin/python3"
        warn "system Python has no pytest; using .venv/bin/python3 for tests"
    else
        PYTEST_READY=0
        fail "pytest is not installed (install python-pytest or create .venv)"
    fi
fi
if [ "$PYTEST_READY" -eq 1 ]; then
    "$PYTHON_BIN" -m pytest -q tests/test_garb.py || fail "garb tests failed"
fi

if [ "$FAILED" -ne 0 ]; then
    die "checks failed"
fi
log "all static checks passed"
