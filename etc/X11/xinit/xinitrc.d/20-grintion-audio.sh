#!/bin/sh
# Grintion-OS per-user audio startup.
#
# The desktop profiles install PipeWire, but this image has no systemd user
# manager to activate pipewire.socket, pipewire-pulse.socket or
# wireplumber.service. Start the three processes explicitly inside the session
# bus. This hook is sourced by LightDM's Xsession and by startx.
if [ "${GRINTION_AUDIO_STARTED:-0}" = "1" ]; then
    return 0 2>/dev/null || exit 0
fi
GRINTION_AUDIO_STARTED=1
export GRINTION_AUDIO_STARTED

if [ -z "${XDG_RUNTIME_DIR:-}" ] || [ ! -d "${XDG_RUNTIME_DIR:-}" ]; then
    XDG_RUNTIME_DIR="/tmp/grintion-runtime-$(id -u)"
    mkdir -p "$XDG_RUNTIME_DIR" 2>/dev/null || {
        return 0 2>/dev/null || exit 0
    }
    chmod 700 "$XDG_RUNTIME_DIR" 2>/dev/null || true
    export XDG_RUNTIME_DIR
fi

# The QEMU HDA codec starts with its output amplifier muted. Unmute the
# common master controls before PipeWire opens the PCM. Missing controls or a
# user outside the audio group are non-fatal; the sink still exists.
if command -v amixer >/dev/null 2>&1; then
    for _control in Master PCM; do
        amixer -c 0 sset "$_control" unmute 100% >/dev/null 2>&1 || true
    done
fi

start_audio_daemon() {
    _name="$1"
    command -v "$_name" >/dev/null 2>&1 || return 0
    pgrep -u "$(id -u)" -x "$_name" >/dev/null 2>&1 && return 0
    "$_name" >>"$XDG_RUNTIME_DIR/$_name.log" 2>&1 &
}

# PipeWire must own its socket before the session manager and PulseAudio
# compatibility daemon connect. Waiting a short bounded time is enough on the
# live image and avoids a permanent race on slow machines.
start_audio_daemon pipewire
_i=0
while [ ! -S "$XDG_RUNTIME_DIR/pipewire-0" ] && [ "$_i" -lt 20 ]; do
    sleep 0.1
    _i=$((_i + 1))
done
start_audio_daemon wireplumber
start_audio_daemon pipewire-pulse
