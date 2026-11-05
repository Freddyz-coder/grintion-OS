#!/bin/sh
# Grintion-OS has no logind or systemd user manager, so nothing provides a
# per-user D-Bus session bus. XFCE's settings daemon, panel and window manager,
# and other desktop services need one; without it the session starts but shows
# "Unable to contact settings server: Could not connect: No such file or
# directory". Start a private bus for this X session, matching the conventional
# /etc/X11/Xsession.d dbus-launch hook used by non-systemd distributions.
if [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ] && command -v dbus-launch >/dev/null 2>&1; then
    eval "$(dbus-launch --sh-syntax --exit-with-session)"
fi
