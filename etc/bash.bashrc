# /etc/bash.bashrc - system-wide interactive bash configuration

# Missing commands are treated as critical, not as a silent dead end. The
# build and boot tests cover the components that must exist; this handler
# explains the common ones a user is likely to type.
command_not_found_handle() {
    printf '[CRITICAL] command not found: %s\n' "$1" >&2
    case "$1" in
        pacman|apk)
            printf 'garb delegates to %s only when it is installed on this system.\n' "$1" >&2 ;;
        clean)
            printf 'clean is not a Grintion-OS command; use clear to clear the screen.\n' >&2 ;;
        man)
            printf 'man pages are not installed in this image.\n' >&2 ;;
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
