# /etc/bash.bashrc - system-wide interactive bash configuration
if [ -n "${BASH_VERSION-}" ]; then
    PS1='\[\033[1;31m\]\u@\h\[\033[0m\]:\[\033[1;34m\]\w\[\033[0m\]\$ '
    HISTSIZE=2000
    HISTFILESIZE=4000
    HISTCONTROL=ignoreboth
    shopt -s checkwinsize
    shopt -s histappend
fi
