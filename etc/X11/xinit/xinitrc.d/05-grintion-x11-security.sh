#!/bin/sh
# Enforce X11 access control for an interactive session.
#
# startx and the display managers already create a per-session cookie. This
# hook makes the boundary explicit: access control stays enabled, the cookie is
# never group/world readable, and no remote host is granted access. It is safe
# to source more than once.
umask 077

if [ -n "${XAUTHORITY:-}" ] && [ -f "$XAUTHORITY" ]; then
    chmod 600 "$XAUTHORITY" 2>/dev/null || true
fi

if command -v xhost >/dev/null 2>&1; then
    xhost - >/dev/null 2>&1 || true
fi
