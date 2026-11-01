#!/bin/sh
# Shared parser for /etc/grintion/network.conf.
#
# The format is deliberately small and comment-friendly:
#
#   [interface enp0s3]
#   mode = dhcp
#
#   [interface enp0s8]
#   mode = static
#   static_ip = 192.168.1.50/24
#   gateway = 192.168.1.1
#   dns = 1.1.1.1, 8.8.8.8
#
#   [wifi]
#   interface = wlan0
#   ssid = MyNetwork
#   psk = passphrase-or-64-hex
#
# Sourced by the network service, the wpa_supplicant service and
# grintion-network. GRINTION_NETWORK_CONF overrides the path for tests.

NETWORK_CONF="${GRINTION_NETWORK_CONF:-/etc/grintion/network.conf}"

network_conf_get() {
    _section="$1"
    _key="$2"
    [ -r "$NETWORK_CONF" ] || return 0
    awk -v section="[$_section]" -v key="$_key" '
        /^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
        /^[[:space:]]*\[/ {
            current = $0
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", current)
            next
        }
        current == section {
            line = $0
            sub(/#.*/, "", line)
            split(line, parts, "=")
            name = parts[1]
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", name)
            if (name == key) {
                value = substr(line, index(line, "=") + 1)
                gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
                print value
                exit
            }
        }
    ' "$NETWORK_CONF"
}

network_sections() {
    [ -r "$NETWORK_CONF" ] || return 0
    awk '
        /^[[:space:]]*\[/ {
            name = $0
            gsub(/^[[:space:]]*\[[[:space:]]*/, "", name)
            gsub(/[[:space:]]*\].*$/, "", name)
            if (name != "") print name
        }
    ' "$NETWORK_CONF"
}

network_interfaces() {
    network_sections | while IFS= read -r section; do
        [ "$section" = "wifi" ] && continue
        printf '%s\n' "$section"
    done
}

network_wifi_configured() {
    [ -n "$(network_conf_get wifi ssid)" ]
}

# Interfaces that dhcpcd can lease an address on.
#
# /sys/class/net also lists kernel pseudo interfaces (sit0, ip6tnl0, tunl0,
# dummy0). They have no link to lease from, and handing them to dhcpcd makes it
# log "unsupported interface type" and delay the real DHCP exchange on eth0,
# which is how a fresh boot ended up with no address (see
# ProblemsWhenInstalling.txt). ARPHRD_ETHER is 1; wireless links are handled by
# the wpa_supplicant service and skipped here.
network_wired_interfaces() {
    _netdir="${GRINTION_SYSFS_NET:-/sys/class/net}"
    for _path in "$_netdir"/*; do
        [ -e "$_path" ] || continue
        _iface="${_path##*/}"
        [ "$_iface" = lo ] && continue
        [ -e "$_path/wireless" ] && continue
        [ -e "$_path/phy80211" ] && continue
        [ "$(cat "$_path/type" 2>/dev/null)" = 1 ] || continue
        printf '%s\n' "$_iface"
    done
}
