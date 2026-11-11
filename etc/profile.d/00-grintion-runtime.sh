# shellcheck shell=sh
# Grintion-OS console session environment.
#
# There is no logind or systemd user manager, so nothing creates per-user
# XDG_RUNTIME_DIR on login. Wayland compositors (sway), PipeWire, WirePlumber
# and D-Bus all refuse to start without it, which made a plain console login
# unable to run 'sway'. Set it once for any login shell.
if [ -z "${XDG_RUNTIME_DIR:-}" ]; then
    _grintion_uid=$(id -u 2>/dev/null) || _grintion_uid=0
    _grintion_runtime="/run/user/$_grintion_uid"
    if [ ! -d "$_grintion_runtime" ] \
        || [ "$(stat -c %u "$_grintion_runtime" 2>/dev/null || echo -1)" != "$_grintion_uid" ]; then
        _grintion_runtime="/tmp/grintion-runtime-$_grintion_uid"
        mkdir -p "$_grintion_runtime" 2>/dev/null || true
    fi
    if [ -d "$_grintion_runtime" ]; then
        chmod 700 "$_grintion_runtime" 2>/dev/null || true
        XDG_RUNTIME_DIR="$_grintion_runtime"
        export XDG_RUNTIME_DIR
    fi
    unset _grintion_uid _grintion_runtime
fi

# libseat reads this socket when a Wayland compositor runs inside a seatd
# session. seatd listens on the default path, so exporting it is only a
# convenience for wrappers that look for the variable first.
if [ -z "${SEATD_SOCK:-}" ] && [ -S /run/seatd.sock ]; then
    SEATD_SOCK=/run/seatd.sock
    export SEATD_SOCK
fi
