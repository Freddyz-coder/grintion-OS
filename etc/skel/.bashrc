# ~/.bashrc - interactive shell configuration
[ -f /etc/bash.bashrc ] && . /etc/bash.bashrc

alias ls='ls --color=auto'
alias grep='grep --color=auto'
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'

if [ -n "${BASH_VERSION-}" ] && [ -f /etc/profile.d/00-grintion.sh ]; then
    . /etc/profile.d/00-grintion.sh
fi
