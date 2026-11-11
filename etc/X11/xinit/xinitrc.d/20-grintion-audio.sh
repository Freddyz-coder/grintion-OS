#!/bin/sh
# Grintion-OS per-user audio startup for X11 sessions.
#
# The helper starts PipeWire, WirePlumber and pipewire-pulse and unmutes every
# ALSA card. This hook is sourced by LightDM's Xsession and by startx. Wayland
# sessions use the same helper from grintion-session or the XDG autostart file.
if [ "${GRINTION_AUDIO_STARTED:-0}" = "1" ]; then
    return 0 2>/dev/null || exit 0
fi
GRINTION_AUDIO_STARTED=1
export GRINTION_AUDIO_STARTED

if command -v grintion-audio >/dev/null 2>&1; then
    grintion-audio --session >/dev/null 2>&1 || true
fi
