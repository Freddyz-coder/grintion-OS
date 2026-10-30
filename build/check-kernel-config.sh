#!/bin/sh
# check-kernel-config.sh - enforce the checked-in kernel configuration contract
#
# Usage: check-kernel-config.sh <final .config> <fragment>
#
# Every CONFIG_* assignment in the fragment must appear in the final .config
# with exactly the requested value. `CONFIG_X=n` is normalized to the
# "# CONFIG_X is not set" form emitted by Kconfig.

set -eu

CONFIG_FILE=${1:?usage: check-kernel-config.sh <config> <fragment>}
FRAGMENT=${2:?usage: check-kernel-config.sh <config> <fragment>}

[ -f "$CONFIG_FILE" ] || { echo "[-] Missing kernel config: $CONFIG_FILE" >&2; exit 1; }
[ -f "$FRAGMENT" ]   || { echo "[-] Missing kernel fragment: $FRAGMENT" >&2; exit 1; }

fail=0
checked=0

while IFS= read -r line; do
    case "$line" in
        CONFIG_*=*)
            sym=${line%%=*}
            want=${line#*=}
            checked=$((checked + 1))

            if grep -qxF "$line" "$CONFIG_FILE"; then
                continue
            fi

            if [ "$want" = "n" ] && grep -qxF "# $sym is not set" "$CONFIG_FILE"; then
                continue
            fi

            actual=$(grep -E "^${sym}=" "$CONFIG_FILE" | head -n 1 || true)
            if [ -z "$actual" ] && grep -qxF "# $sym is not set" "$CONFIG_FILE"; then
                actual="# $sym is not set"
            fi
            printf '[-] kernel config mismatch: %s wants %s, got %s\n' \
                "$sym" "$want" "${actual:-<absent>}" >&2
            fail=1
            ;;
    esac
done < "$FRAGMENT"

if [ "$fail" -ne 0 ]; then
    echo "[-] Kernel configuration contract failed ($checked options checked)." >&2
    exit 1
fi

echo "[+] Kernel configuration contract satisfied ($checked options checked)."
