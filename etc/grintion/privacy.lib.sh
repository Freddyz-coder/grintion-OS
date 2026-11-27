# Grintion-OS privacy defaults shared by the interactive shell startup files.
#
# Shell history is kept in RAM for the current boot only. It is shared by all
# terminals of the same user (so up-arrow and `history` keep working) but is
# never written to disk, and it disappears on reboot. If /dev/shm is not a
# tmpfs, the shell falls back to no history rather than writing to the root
# filesystem.
#
# The same directory holds the history/state files of common tools that would
# otherwise create dotfiles in $HOME: sqlite3, psql, mysql, redis-cli, gdb,
# Node's REPL and Python's readline history. Vim's viminfo is handled by
# /etc/vimrc because it needs a Vim option, not an environment variable.
#
# GRINTION_HISTORY_DIR overrides the tmpfs root for tests and recovery. The
# override is still subject to the tmpfs and ownership checks below.

grintion_private_tool_state() {
    _grintion_private=$1
    _grintion_directory=$2

    if [ "$_grintion_private" = 1 ]; then
        : "${SQLITE_HISTORY:=$_grintion_directory/sqlite_history}"
        : "${PSQL_HISTORY:=$_grintion_directory/psql_history}"
        : "${MYSQL_HISTFILE:=$_grintion_directory/mysql_history}"
        : "${REDISCLI_HISTFILE:=$_grintion_directory/redis_history}"
        : "${GDBHISTFILE:=$_grintion_directory/gdb_history}"
        : "${NODE_REPL_HISTORY:=$_grintion_directory/node_history}"
        : "${PYTHON_HISTORY:=$_grintion_directory/python_history}"
    else
        # Fail closed: no tmpfs means no per-tool history, not a $HOME dotfile.
        : "${SQLITE_HISTORY:=/dev/null}"
        : "${PSQL_HISTORY:=/dev/null}"
        : "${MYSQL_HISTFILE:=/dev/null}"
        : "${REDISCLI_HISTFILE:=/dev/null}"
        : "${GDBHISTFILE:=/dev/null}"
        : "${NODE_REPL_HISTORY:=/dev/null}"
        : "${PYTHON_HISTORY:=/dev/null}"
    fi

    export SQLITE_HISTORY PSQL_HISTORY MYSQL_HISTFILE REDISCLI_HISTFILE
    export GDBHISTFILE NODE_REPL_HISTORY PYTHON_HISTORY
}

grintion_private_history() {
    grintion_uid=$(id -u 2>/dev/null)
    [ -n "$grintion_uid" ] || grintion_uid=unknown
    hist_root=${GRINTION_HISTORY_DIR:-/dev/shm}
    hist_dir="$hist_root/.grintion-history-$grintion_uid"
    private=0

    LESSHISTFILE=-

    # Fail closed: do not create history files on a disk-backed directory.
    if [ "$(stat -f -c %T "$hist_root" 2>/dev/null)" = tmpfs ]; then
        if [ ! -L "$hist_dir" ] && [ -d "$hist_dir" ] &&
            [ "$(stat -c %u "$hist_dir" 2>/dev/null)" = "$grintion_uid" ] &&
            chmod 700 "$hist_dir" 2>/dev/null; then
            private=1
        elif [ ! -e "$hist_dir" ] && (umask 077; mkdir "$hist_dir") 2>/dev/null; then
            private=1
        fi
    fi

    if [ -n "${BASH_VERSION-}" ]; then
        HISTFILE=/dev/null
        if [ "$private" = 1 ]; then
            HISTFILE="$hist_dir/history"
            # Pre-create 0600 rather than letting bash use the process umask.
            (umask 077; : >> "$HISTFILE") 2>/dev/null || HISTFILE=/dev/null
            chmod 600 "$HISTFILE" 2>/dev/null || HISTFILE=/dev/null
        fi
        export HISTFILE
        # Concurrent terminals append instead of replacing each other's history.
        [ "$HISTFILE" != /dev/null ] && shopt -s histappend 2>/dev/null
    fi

    grintion_private_tool_state "$private" "$hist_dir"
    export LESSHISTFILE
    unset grintion_uid hist_root hist_dir private
    return 0
}
