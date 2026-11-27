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
    awk -v section="$_section" -v key="$_key" '
        /^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
        /^[[:space:]]*\[/ {
            current = $0
            gsub(/^[[:space:]]*\[/, "", current)
            gsub(/\][[:space:]]*$/, "", current)
            next
        }
        # Sections are written as [interface eth0], but callers in the boot
        # service pass the bare interface name. Accept both spellings.
        current == section || current == "interface " section {
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
        # Return the bare device name; network_conf_get accepts either form.
        printf '%s\n' "${section#interface }"
    done
}

network_wifi_configured() {
    [ -n "$(network_conf_get wifi ssid)" ]
}

# MAC randomization policy for a section:
#   stable (default) - one random address per interface or per Wi-Fi SSID,
#                      kept across reboots. This hides the vendor OUI without
#                      breaking DHCP reservations, captive portals or switch
#                      port-security, which a new address every boot would.
#   random           - a fresh random address on every boot (strongest
#                      unlinkability, but new DHCP lease each time).
#   off              - the hardware address.
network_mac_randomization_mode() {
    case "$(network_conf_get "$1" mac_randomize)" in
        false|off|no|0) printf 'off\n' ;;
        true|random|yes|1) printf 'random\n' ;;
        *) printf 'stable\n' ;;
    esac
}

# random_local_mac prints a locally administered, unicast MAC address.
# The first octet has bit 1 set (locally administered) and bit 0 clear
# (unicast); the rest comes from the kernel CSPRNG. Used for mac_randomize =
# true and as the fallback when no stable seed can be stored.
random_local_mac() {
    _bytes=$(od -An -N5 -tu1 /dev/urandom 2>/dev/null) || return 1
    # shellcheck disable=SC2086
    set -- $_bytes
    [ $# -eq 5 ] || return 1
    printf '02:%02x:%02x:%02x:%02x:%02x\n' "$1" "$2" "$3" "$4" "$5"
}

# Per-install seed for stable MACs. Keeping it under /var (0700/0600) means two
# machines built from the same image do not share addresses; on a live session
# /var is the RAM overlay, so the address is fresh per boot and still stable
# while the session lasts.
GRINTION_PRIVACY_DIR="${GRINTION_PRIVACY_DIR:-/var/lib/grintion/privacy}"

ensure_mac_seed() {
    _seed="$GRINTION_PRIVACY_DIR/mac-seed"
    if [ ! -s "$_seed" ]; then
        (umask 077; mkdir -p "$GRINTION_PRIVACY_DIR") 2>/dev/null || return 1
        _tmp="$_seed.$$"
        if ! (umask 077; od -An -N16 -tx1 /dev/urandom 2>/dev/null | tr -d '[:space:]' > "$_tmp") || [ ! -s "$_tmp" ]; then
            rm -f "$_tmp"
            return 1
        fi
        # Link without replacing: if the other network service created the seed
        # first, both use that file instead of racing to overwrite it.
        ln "$_tmp" "$_seed" 2>/dev/null || true
        rm -f "$_tmp"
        [ -s "$_seed" ] || return 1
    fi
    printf '%s\n' "$_seed"
}

# stable_local_mac KEY prints the same locally administered address for the
# same KEY on this install. The seed is hashed with the interface name or SSID,
# so different networks cannot correlate the client, while the hardware address
# is never exposed.
stable_local_mac() {
    _mac_key="$1"
    command -v sha256sum >/dev/null 2>&1 || return 1
    _seed_path=$(ensure_mac_seed) || return 1
    _seed_value=$(cat "$_seed_path" 2>/dev/null) || return 1
    [ -n "$_seed_value" ] || return 1
    _mac_hex=$(printf '%s:%s' "$_seed_value" "$_mac_key" | sha256sum 2>/dev/null | cut -c1-10)
    [ ${#_mac_hex} -eq 10 ] || return 1
    # 02 keeps the address unicast and locally administered; five bytes vary.
    printf '02:%s\n' "$(printf '%s' "$_mac_hex" | sed 's/../&:/g; s/:$//')"
}

# Global wpa_supplicant lines for scan privacy. The association address is set
# on the interface by the service (see etc/sv/wpa_supplicant/run), which needs
# no wpa_supplicant MAC feature; preassoc_mac_addr is accepted globally by
# current releases and hides the address during scans and ANQP.
network_wifi_mac_lines() {
    [ "$(network_mac_randomization_mode wifi)" = off ] && return 0
    printf 'preassoc_mac_addr=1\n'
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
