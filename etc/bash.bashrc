# /etc/bash.bashrc - system-wide interactive bash configuration

# Missing commands are treated as critical, not as a silent dead end. The
# build and boot tests cover the components that must exist; this handler
# explains the common ones a user is likely to type.
command_not_found_handle() {
    printf '[CRITICAL] command not found: %s\n' "$1" >&2
    case "$1" in
        startx|sway|xfce4-session|gnome-session|startplasma-x11|startlxqt|i3)
            printf 'A graphical desktop is not installed yet. Run "sudo grintion-desktop install" to set up a GUI.\n' >&2 ;;
        apk)
            printf 'garb delegates to apk only when an apk binary is present.\n' >&2 ;;
        clean)
            printf 'clean is not a Grintion-OS command; use clear to clear the screen.\n' >&2 ;;
        man)
            printf 'man pages are not installed in this base image; install with "garb install man-db man-pages".\n' >&2 ;;
    esac
    return 127
}

if [ -n "${BASH_VERSION-}" ]; then
    PS1='\[\033[1;31m\]\u@\h\[\033[0m\]:\[\033[1;34m\]\w\[\033[0m\]\$ '
    HISTSIZE=2000
    HISTFILESIZE=4000
    HISTCONTROL=ignoreboth
    shopt -s checkwinsize
    shopt -s histappend
fi
