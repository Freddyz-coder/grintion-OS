# ~/.bash_profile - login shell startup
if [ -f ~/.bashrc ]; then
    . ~/.bashrc
fi
if [ -f /etc/profile ]; then
    . /etc/profile
fi
