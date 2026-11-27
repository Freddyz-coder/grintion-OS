# Grintion-OS privacy default: interactive history is RAM-backed for this
# boot only. It is shared between terminals of the same user, so up-arrow and
# `history` keep working, but it never reaches disk and is gone after reboot.
#
# To keep a disk-backed history for one account, set HISTFILE in ~/.bashrc
# after this profile is read. Sudo I/O logging and auditd are independent of
# shell history and remain enabled.
#
# If /dev/shm is not a tmpfs, history is disabled rather than written to the
# root filesystem.

if [ -r /etc/grintion/privacy.lib.sh ]; then
    . /etc/grintion/privacy.lib.sh
    grintion_private_history
fi
