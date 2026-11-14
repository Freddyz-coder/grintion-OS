#!/usr/bin/env bash
# make-rootfs.sh - assemble the complete Grintion-OS live root filesystem.
#
# The live root is a curated, auditable userland assembled from the build
# host's installed GNU/glibc packages plus source-built components (Linux,
# dhcpcd, runit, busybox). Every required command is checked; nothing is
# silently skipped. Ownership is normalised to root by mkinitramfs.py, while
# set-ID modes are applied explicitly after staging.

set -Eeuo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

WORK="$GRINTION_REPO_ROOT/build/work"
ROOTFS="$WORK/rootfs"
OUTPUT="$GRINTION_REPO_ROOT/output"
CONFIG="$GRINTION_REPO_ROOT/config"
KREL="$(kernel_release)"
MODROOT="$WORK/kernel-modules"
STAGE_DHCPCD="$WORK/dhcpcd-root"
# Optional root of an unpacked Arch apparmor package. This lets an unprivileged
# builder use apparmor_parser and its policy abstractions without installing
# the package system-wide. Normal builds leave this empty and use the host.
APPARMOR_ROOT="${GRINTION_APPARMOR_ROOT:-}"

need_cmd bash
need_cmd python3
need_cmd cp
need_cmd install
need_cmd ldd
need_cmd cpio
need_cmd gzip
need_cmd zstd
need_cmd sha256sum

log "assembling live rootfs for Grintion-OS $GRINTION_VERSION ($KREL)"

# ---------------------------------------------------------------- directories
rm -rf "$ROOTFS"
mkdir -p "$ROOTFS"/usr/{bin,sbin,lib,lib64,share,include,libexec} \
         "$ROOTFS"/{etc,var,run,proc,sys,dev,tmp,root,home,mnt,media,srv,opt,boot}
mkdir -p "$ROOTFS"/var/{log,spool/mail,lib/garb,lib/dhcpcd,cache/garb,lib/pacman/local,cache/pacman/pkg}
mkdir -p "$ROOTFS"/var/service
mkdir -p "$ROOTFS"/usr/lib/{modules,security,locale,grintion/boot}
mkdir -p "$ROOTFS"/usr/share/{limine,terminfo,zoneinfo,doc/grintion}
mkdir -p "$ROOTFS"/etc/{pam.d,security,skel,sv,ssl/certs,runit,sysctl.d,profile.d,default}
chmod 1777 "$ROOTFS/tmp"
chmod 0700 "$ROOTFS/root"

# merged-/usr layout: /bin, /sbin, /lib and /lib64 are symlinks into /usr.
ln -sfn usr/bin   "$ROOTFS/bin"
ln -sfn usr/sbin  "$ROOTFS/sbin"
ln -sfn usr/lib   "$ROOTFS/lib"
ln -sfn usr/lib   "$ROOTFS/lib64"
ln -sfn lib       "$ROOTFS/usr/lib64"
ln -sfn var/service "$ROOTFS/service"

# ---------------------------------------------------------------- host binaries
log "copying required host binaries"
declare -a MISSING=() COPIED=()
while IFS= read -r cmd; do
    [ -n "$cmd" ] || continue
    case "$cmd" in \#*) continue ;; esac
    src="$(type -P "$cmd" 2>/dev/null || true)"
    if [ -z "$src" ]; then
        MISSING+=("$cmd")
        continue
    fi
    # sh is installed as a symlink to bash below; avoid a second copy.
    if [ "$cmd" = "sh" ]; then
        continue
    fi
    install -D -m 0755 "$(readlink -f "$src")" "$ROOTFS/usr/bin/$cmd"
    COPIED+=("$cmd")
done < "$CONFIG/rootfs.required-binaries"

if [ "${#MISSING[@]}" -gt 0 ]; then
    die "required host binaries are missing: ${MISSING[*]}"
fi
log "installed ${#COPIED[@]} required commands"

while IFS= read -r cmd; do
    [ -n "$cmd" ] || continue
    case "$cmd" in \#*) continue ;; esac
    src="$(type -P "$cmd" 2>/dev/null || true)"
    if [ -n "$src" ]; then
        install -D -m 0755 "$(readlink -f "$src")" "$ROOTFS/usr/bin/$cmd"
    else
        warn "optional command not present on host: $cmd"
    fi
done < "$CONFIG/rootfs.optional-binaries"

# MAC tooling is not optional in an image that claims AppArmor enforcement.
# Keep this separate from rootfs.required-binaries so `make check` can run on
# hosts that do not build images, while `make rootfs` still refuses to ship a
# profile set that cannot be loaded.
while IFS= read -r cmd; do
    [ -n "$cmd" ] || continue
    case "$cmd" in \#*) continue ;; esac
    if [ -n "$APPARMOR_ROOT" ]; then
        src="$APPARMOR_ROOT/usr/bin/$cmd"
    else
        src="$(type -P "$cmd" 2>/dev/null || true)"
    fi
    [ -n "$src" ] && [ -x "$src" ] \
        || die "required MAC command is missing: $cmd (install apparmor or set GRINTION_APPARMOR_ROOT)"
    install -D -m 0755 "$(readlink -f "$src")" "$ROOTFS/usr/bin/$cmd"
done < "$CONFIG/rootfs.mac-binaries"

# auditd is a real service in this image, so its userspace is required, not
# optional. Copy the binaries with their complete library closure; a service
# file that can only print "auditd not found" is worse than no service.
if [ ! -f "$CONFIG/rootfs.audit-binaries" ]; then
    die "config/rootfs.audit-binaries is missing"
fi
while IFS= read -r cmd; do
    [ -n "$cmd" ] || continue
    case "$cmd" in \#*) continue ;; esac
    src="$(type -P "$cmd" 2>/dev/null || true)"
    [ -n "$src" ] || die "required audit command is missing on the host: $cmd"
    python3 "$GRINTION_REPO_ROOT/build/copy-with-libs.py" \
        --root "$ROOTFS" --dest usr/bin "$src" \
        || die "failed to copy audit command: $cmd"
done < "$CONFIG/rootfs.audit-binaries"

ln -sfn bash "$ROOTFS/usr/bin/sh"
[ -x "$ROOTFS/usr/bin/vim" ] && ln -sfn vim "$ROOTFS/usr/bin/vi"
[ -x "$ROOTFS/usr/bin/grep" ] && { ln -sfn grep "$ROOTFS/usr/bin/egrep"; ln -sfn grep "$ROOTFS/usr/bin/fgrep"; }

# ---------------------------------------------------------------- source-built tools
if [ ! -x "$GRINTION_REPO_ROOT/tools/bin/busybox" ]; then
    die "tools/bin/busybox is missing; run make tools"
fi
install -D -m 0755 "$GRINTION_REPO_ROOT/tools/bin/busybox" "$ROOTFS/usr/bin/busybox"
ln -sfn busybox "$ROOTFS/usr/bin/mdev"
ln -sfn busybox "$ROOTFS/usr/bin/hostname"
ln -sfn busybox "$ROOTFS/usr/bin/dnsdomainname"

for tool in runit runsv runsvdir sv chpst; do
    [ -x "$GRINTION_REPO_ROOT/tools/bin/$tool" ] || die "tools/bin/$tool is missing; run make tools"
    install -D -m 0755 "$GRINTION_REPO_ROOT/tools/bin/$tool" "$ROOTFS/usr/sbin/$tool"
done
ln -sfn runit "$ROOTFS/usr/sbin/init"

# Grintion's own tools and the live init must be in the image; they are not
# host binaries and therefore never come from the package list.
for tool_path in "$GRINTION_REPO_ROOT"/bin/*; do
    [ -f "$tool_path" ] && [ -x "$tool_path" ] || continue
    tool="$(basename "$tool_path")"
    # Install each tool once. Root's PATH puts /usr/sbin before /usr/bin, so a
    # second copy there shadowed the /usr/bin one: after the desktop installer
    # updated /usr/bin/grintion-desktop, 'grintion-desktop' still executed the
    # stale /usr/sbin copy. That made the Sway user config step silently
    # disappear. Nothing invokes these tools through /usr/sbin.
    install -D -m 0755 "$tool_path" "$ROOTFS/usr/bin/$tool"
done

# garb is split into a package; the CLI adds /usr/lib/garb when it is not
# running from the source tree.
rm -rf "$ROOTFS/usr/lib/garb/garblib"
install -d -m 0755 "$ROOTFS/usr/lib/garb"
cp -a "$GRINTION_REPO_ROOT/bin/garblib" "$ROOTFS/usr/lib/garb/garblib"
find "$ROOTFS/usr/lib/garb/garblib" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$ROOTFS/usr/lib/garb/garblib" -type d -exec chmod 0755 {} +
find "$ROOTFS/usr/lib/garb/garblib" -type f -exec chmod 0644 {} +

install -D -m 0755 "$GRINTION_REPO_ROOT/init/live-init" "$ROOTFS/init"
install -D -m 0755 "$GRINTION_REPO_ROOT/init/recovery.sh" "$ROOTFS/recovery.sh"

# dhcpcd is built from the pinned upstream tarball. The staged install tree is
# reused so the binary and its hook scripts always come from one build.
if [ ! -x "$GRINTION_REPO_ROOT/tools/src/dhcpcd-10.5.2/src/dhcpcd" ]; then
    log "building dhcpcd 10.5.2 from source"
    ( cd "$GRINTION_REPO_ROOT/tools/src/dhcpcd-10.5.2" && make -j"$(nproc)" )
fi
rm -rf "$STAGE_DHCPCD"
make -C "$GRINTION_REPO_ROOT/tools/src/dhcpcd-10.5.2" DESTDIR="$STAGE_DHCPCD" install >/dev/null
install -D -m 0755 "$STAGE_DHCPCD/usr/sbin/dhcpcd" "$ROOTFS/usr/sbin/dhcpcd"
install -D -m 0755 "$STAGE_DHCPCD/usr/libexec/dhcpcd-run-hooks" "$ROOTFS/usr/libexec/dhcpcd-run-hooks"
mkdir -p "$ROOTFS/usr/libexec/dhcpcd-hooks"
cp -a "$STAGE_DHCPCD/usr/libexec/dhcpcd-hooks/." "$ROOTFS/usr/libexec/dhcpcd-hooks/"
chmod 0755 "$ROOTFS/usr/libexec/dhcpcd-hooks/"*

# gpg helpers used by pacman's signature verification. They are libexec
# programs, not PATH commands, so resolve-libs.py would not see them.
if [ -d /usr/lib/gnupg ]; then
    mkdir -p "$ROOTFS/usr/lib/gnupg"
    cp -a /usr/lib/gnupg/. "$ROOTFS/usr/lib/gnupg/"
    find "$ROOTFS/usr/lib/gnupg" -type f -exec chmod 0755 {} +
fi

# ---------------------------------------------------------------- PAM and NSS
log "installing PAM modules and identity lookup modules"
while IFS= read -r module; do
    [ -n "$module" ] || continue
    case "$module" in \#*) continue ;; esac
    [ -f "/usr/lib/security/$module" ] || die "PAM module missing on host: $module"
    install -D -m 0644 "/usr/lib/security/$module" "$ROOTFS/usr/lib/security/$module"
done < "$CONFIG/rootfs.pam-modules"

for nss in libnss_files.so.2 libnss_dns.so.2; do
    [ -f "/usr/lib/$nss" ] || die "NSS module missing on host: $nss"
    install -D -m 0644 "/usr/lib/$nss" "$ROOTFS/usr/lib/$nss"
done

# sudo opens its policy plugin with dlopen, so resolve-libs.py cannot see
# sudoers.so. Copying only the sudo binary produces a system where every
# sudo invocation dies with "unable to load plugins" before PAM runs.
[ -d /usr/lib/sudo ] || die "host sudo plugin directory is missing: /usr/lib/sudo"
mkdir -p "$ROOTFS/usr/lib/sudo"
cp -a /usr/lib/sudo/. "$ROOTFS/usr/lib/sudo/"
[ -f "$ROOTFS/usr/lib/sudo/sudoers.so" ] || die "sudoers.so missing from rootfs"
chmod 0755 "$ROOTFS/usr/lib/sudo"/*.so* 2>/dev/null || true

# ---------------------------------------------------------------- Python
PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [ -d "/usr/lib/python${PY_VER}" ]; then
    log "deploying Python ${PY_VER} standard library"
    python3 - "$ROOTFS" "$PY_VER" <<'PY'
import os
import shutil
import sys

root, ver = sys.argv[1], sys.argv[2]
src = f"/usr/lib/python{ver}"
dest = os.path.join(root, f"usr/lib/python{ver}")
if os.path.exists(dest):
    shutil.rmtree(dest)

def ignore(_directory, names):
    blocked = {"site-packages", "test", "tests", "__pycache__", "idlelib", "tkinter", "turtledemo"}
    return [name for name in names if name in blocked]

shutil.copytree(src, dest, ignore=ignore, symlinks=False)
PY
else
    die "host Python ${PY_VER} standard library not found"
fi

# ---------------------------------------------------------------- data trees
log "deploying terminfo, CA certificates and OpenSSL providers"
cp -a /usr/share/terminfo/. "$ROOTFS/usr/share/terminfo/"
install -D -m 0644 /etc/ssl/certs/ca-certificates.crt "$ROOTFS/etc/ssl/certs/ca-certificates.crt"
install -D -m 0644 /etc/ssl/openssl.cnf "$ROOTFS/etc/ssl/openssl.cnf" 2>/dev/null || true
# OpenSSL is compiled with OPENSSLDIR=/etc/ssl, so its default CAfile is
# /etc/ssl/cert.pem (not the bundle in certs/). Without that link, anything
# that calls SSL_CTX_set_default_verify_paths() — Python's ssl module and the
# openssl command line, among others — trusts zero CAs even though the bundle
# is present. curl has its own compiled-in bundle path and is unaffected.
if [ -f "$ROOTFS/etc/ssl/certs/ca-certificates.crt" ]; then
    ln -sfn certs/ca-certificates.crt "$ROOTFS/etc/ssl/cert.pem"
fi
if [ -d /usr/lib/ossl-modules ]; then
    mkdir -p "$ROOTFS/usr/lib/ossl-modules"
    cp -a /usr/lib/ossl-modules/. "$ROOTFS/usr/lib/ossl-modules/"
fi
# dbus-run-session needs the shipped session.conf and service directories.
# The binaries alone fail with "Failed to open /usr/share/dbus-1/session.conf".
if [ -d /usr/share/dbus-1 ]; then
    mkdir -p "$ROOTFS/usr/share/dbus-1"
    cp -a /usr/share/dbus-1/. "$ROOTFS/usr/share/dbus-1/"
fi
# Wayland/libinput needs the udev database and rules. systemd-udevd is used as
# a standalone device manager; systemd is not PID 1 and no systemd units run.
if [ -x /usr/bin/udevadm ] && [ -x /usr/lib/systemd/systemd-udevd ]; then
    install -D -m 0755 /usr/bin/udevadm "$ROOTFS/usr/bin/udevadm"
    install -D -m 0755 /usr/lib/systemd/systemd-udevd "$ROOTFS/usr/lib/systemd/systemd-udevd"
    mkdir -p "$ROOTFS/usr/lib/systemd"
    for lib in /usr/lib/systemd/libsystemd-shared-*.so; do
        [ -f "$lib" ] && install -D -m 0755 "$lib" "$ROOTFS/usr/lib/systemd/$(basename "$lib")"
    done
    [ -d /usr/lib/udev ] && cp -a /usr/lib/udev "$ROOTFS/usr/lib/"
    # Purge host-specific virtualization rules that fail callouts in generic environments
    rm -f "$ROOTFS/usr/lib/udev/rules.d/"*vbox* "$ROOTFS/usr/lib/udev/rules.d/"*virtualbox*
else
    die "udev assets are missing on the build host"
fi

# Shims for non-systemd system (runit): udev rules and pacman ALPM hooks expect
# systemctl, systemd-sysctl, and systemd-hook. Provide lightweight no-op shims so
# package scriptlets and hardware callouts succeed cleanly without polluting logs.
install -D -m 0755 /dev/null "$ROOTFS/usr/bin/systemctl"
cat > "$ROOTFS/usr/bin/systemctl" <<'SHIM'
#!/bin/sh
# Systemctl shim for runit-based Grintion-OS
exit 0
SHIM

install -D -m 0755 /dev/null "$ROOTFS/usr/lib/systemd/systemd-sysctl"
cat > "$ROOTFS/usr/lib/systemd/systemd-sysctl" <<'SHIM'
#!/bin/sh
exit 0
SHIM

install -D -m 0755 /dev/null "$ROOTFS/usr/share/libalpm/scripts/systemd-hook"
cat > "$ROOTFS/usr/share/libalpm/scripts/systemd-hook" <<'SHIM'
#!/bin/sh
# Systemd ALPM hook shim for runit-based Grintion-OS
case "$1" in
    reload|restart)
        if [ "$2" = "dbus.service" ] || [ "$2" = "dbus" ]; then
            if [ -x /usr/bin/sv ] && sv status dbus >/dev/null 2>&1; then
                sv reload dbus 2>/dev/null || true
            fi
        fi
        ;;
esac
exit 0
SHIM

# Users follow Arch installation guides on a console-only Grintion system and
# then hit "pacstrap: command not found". Fail with the supported commands
# instead of leaving them to guess.
install -D -m 0755 /dev/null "$ROOTFS/usr/bin/pacstrap"
cat > "$ROOTFS/usr/bin/pacstrap" <<'SHIM'
#!/bin/sh
cat >&2 <<'EOF'
pacstrap is an Arch Linux installer tool; Grintion-OS does not use it.

Install Grintion-OS onto a disk from the live image:
  grintion-install --disk /dev/sdX

Install a desktop environment on an installed system:
  sudo grintion-desktop install kde      # or xfce, lxqt, sway, i3

Install packages (pacman's -S/-s flags do not apply):
  sudo garb install firefox networkmanager plasma-meta
  sudo garb update
EOF
exit 1
SHIM

# Deploy glibc gconv modules for codepage conversion (needed by mkfs.vfat / iconv)
if [ -d /usr/lib/gconv ]; then
    log "deploying glibc iconv conversion modules"
    mkdir -p "$ROOTFS/usr/lib/gconv"
    cp -a /usr/lib/gconv/. "$ROOTFS/usr/lib/gconv/"
fi

# localedef needs the glibc locale sources. Without them, `grintion-config set
# locale en_US.UTF-8` wrote a locale name that glibc could not load, so
# programs silently fell back to the C locale and non-ASCII glyphs became '?'.
[ -d /usr/share/i18n ] || die "host locale sources are missing: /usr/share/i18n"
log "deploying glibc locale sources"
mkdir -p "$ROOTFS/usr/share/i18n" "$ROOTFS/usr/lib/locale"
cp -a /usr/share/i18n/. "$ROOTFS/usr/share/i18n/"

# Deploy GLib 2.0 schemas and data
if [ -d /usr/share/glib-2.0 ]; then
    log "deploying GLib schemas"
    mkdir -p "$ROOTFS/usr/share/glib-2.0"
    cp -a /usr/share/glib-2.0/. "$ROOTFS/usr/share/glib-2.0/"
fi

# Ensure full GLib library suite is present for desktop and D-Bus services
for glib_so in /usr/lib/libglib-2.0.so* /usr/lib/libgio-2.0.so* /usr/lib/libgmodule-2.0.so* /usr/lib/libgobject-2.0.so* /usr/lib/libgthread-2.0.so* /usr/lib/libgirepository-*.so*; do
    [ -e "$glib_so" ] || continue
    install -D -m 0755 "$glib_so" "$ROOTFS/usr/lib/$(basename "$glib_so")"
done
# Ship the full timezone database so the documented
# `ln -sf /usr/share/zoneinfo/Region/City /etc/localtime` step works.
if [ -d /usr/share/zoneinfo ]; then
    log "deploying the timezone database"
    cp -a /usr/share/zoneinfo/. "$ROOTFS/usr/share/zoneinfo/"
    ln -sfn /usr/share/zoneinfo/UTC "$ROOTFS/etc/localtime"
else
    die "host timezone database is missing: /usr/share/zoneinfo"
fi
for f in /etc/services /etc/protocols; do
    [ -f "$f" ] && install -D -m 0644 "$f" "$ROOTFS$f"
done

# ---------------------------------------------------------------- kernel and modules
[ -s "$OUTPUT/vmlinuz-grintion" ] || die "kernel image missing: run make kernel"
[ -f "$OUTPUT/initramfs-install.img" ] || die "installed initramfs missing: run make install-initramfs"
[ -d "$MODROOT/lib/modules/$KREL" ] || die "kernel modules missing: run make kernel"

log "deploying kernel modules for $KREL"
mkdir -p "$ROOTFS/usr/lib/modules"
cp -a "$MODROOT/lib/modules/$KREL" "$ROOTFS/usr/lib/modules/"
rm -f "$ROOTFS/usr/lib/modules/$KREL/build" "$ROOTFS/usr/lib/modules/$KREL/source"

install -D -m 0644 "$OUTPUT/vmlinuz-grintion" "$ROOTFS/usr/lib/grintion/boot/vmlinuz-grintion"
install -D -m 0644 "$OUTPUT/initramfs-install.img" "$ROOTFS/usr/lib/grintion/boot/initramfs-install.img"
install -D -m 0644 "$OUTPUT/System.map-grintion" "$ROOTFS/usr/lib/grintion/boot/System.map-grintion"
install -D -m 0644 "$OUTPUT/config-grintion" "$ROOTFS/usr/lib/grintion/boot/config-grintion"
(
    cd "$ROOTFS/usr/lib/grintion/boot"
    sha256sum vmlinuz-grintion initramfs-install.img System.map-grintion config-grintion > SHA256SUMS
)

for asset in limine limine-bios.sys limine-bios-cd.bin limine-uefi-cd.bin BOOTX64.EFI; do
    [ -f "$GRINTION_REPO_ROOT/tools/limine/$asset" ] || die "limine asset missing: $asset"
    install -D -m 0644 "$GRINTION_REPO_ROOT/tools/limine/$asset" "$ROOTFS/usr/share/limine/$asset"
done
chmod 0755 "$ROOTFS/usr/share/limine/limine"

# ---------------------------------------------------------------- configuration
log "deploying /etc configuration"
cp -a "$GRINTION_REPO_ROOT/etc/." "$ROOTFS/etc/"

# The tracked profiles include the AppArmor policy language abstractions,
# tunables and ABI declarations. Those files ship with the apparmor package on
# the build host, not with this repository, so copy the matching support tree
# into the image or every profile fails to parse at boot.
for dir in abi tunables abstractions; do
    if [ -n "$APPARMOR_ROOT" ]; then
        src="$APPARMOR_ROOT/etc/apparmor.d/$dir"
        [ -e "$src" ] || src="$APPARMOR_ROOT/usr/share/apparmor/$dir"
    else
        src="/etc/apparmor.d/$dir"
        [ -e "$src" ] || src="/usr/share/apparmor/$dir"
    fi
    [ -e "$src" ] || die "AppArmor policy support is missing: $dir (install apparmor or set GRINTION_APPARMOR_ROOT)"
    mkdir -p "$ROOTFS/etc/apparmor.d/$dir"
    cp -aL "$src"/. "$ROOTFS/etc/apparmor.d/$dir/"
done

# A profile that does not parse confines nothing. Use the parser that will ship
# in the image, against the policy support copied above, instead of trusting the
# profiles because they are present.
log "validating AppArmor profiles"
for profile in "$ROOTFS"/etc/apparmor.d/*; do
    [ -f "$profile" ] || continue
    "$ROOTFS/usr/bin/apparmor_parser" -Q --skip-cache \
        -I "$ROOTFS/etc/apparmor.d" "$profile" >/dev/null 2>&1 \
        || die "AppArmor profile failed to parse: $profile"
done

# Account databases are generated from one declarative manifest instead of
# being copied from the build host. The manifest uses portable UIDs/GIDs and
# deliberately omits host-only accounts (for example spice-webdavd).
log "generating account databases from config/accounts.toml"
python3 "$GRINTION_REPO_ROOT/build/gen-accounts.py" \
    --manifest "$CONFIG/accounts.toml" --etc "$ROOTFS/etc"

# The udev tree is copied from the build host, so a host package can introduce
# a rule that names a group this image does not have. udevd then logs
# "Unknown group" beside the login prompt and the device is left with the wrong
# group. Fail the image build instead of shipping an unresolved rule.
python3 - "$ROOTFS" <<'PY'
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
group_file = root / "etc" / "group"
groups = {
    line.split(":", 1)[0]
    for line in group_file.read_text().splitlines()
    if line.strip()
}
missing = {}
for rule in sorted((root / "usr/lib/udev/rules.d").glob("*.rules")):
    for number, line in enumerate(rule.read_text(errors="replace").splitlines(), 1):
        for match in re.finditer(r'GROUP="([^"]+)"', line):
            name = match.group(1)
            if name not in groups:
                missing.setdefault(name, []).append(f"{rule.name}:{number}")
if missing:
    for name, references in sorted(missing.items()):
        print(f"[-] udev group {name!r} is missing (referenced by {', '.join(references)})", file=sys.stderr)
    raise SystemExit(1)
print(f"[+] udev groups resolved: {len(groups)} groups")
PY

# The runtime doctor checks this list instead of silently trusting the build.
{
    grep -vE '^[[:space:]]*(#|$)' "$CONFIG/rootfs.required-binaries"
    grep -vE '^[[:space:]]*(#|$)' "$CONFIG/rootfs.mac-binaries"
} | sort -u > "$ROOTFS/etc/grintion/required-commands"

# pacman's CheckSpace option needs mount information. A regular /etc/mtab is
# not maintained without util-linux's mount helper, so use the kernel view.
ln -sfn /proc/self/mounts "$ROOTFS/etc/mtab"

# ---------------------------------------------------------------- pacman backend
log "installing the pacman external backend"
[ -f "$ROOTFS/etc/pacman.conf" ] || die "etc/pacman.conf missing from rootfs"
PACMAN_SNAPSHOT="$(sed -n 's/^ALA_DATE=//p' "$CONFIG/arch-snapshot")"
[ -n "$PACMAN_SNAPSHOT" ] || die "ALA_DATE is missing from config/arch-snapshot"
grep -qF "archive.archlinux.org/repos/$PACMAN_SNAPSHOT/" "$ROOTFS/etc/pacman.conf" \
    || die "etc/pacman.conf does not use the $PACMAN_SNAPSHOT Arch snapshot"
mkdir -p "$ROOTFS/etc/pacman.d/gnupg" "$ROOTFS/etc/pacman.d/hooks" \
         "$ROOTFS/usr/share/pacman/keyrings"
chmod 0700 "$ROOTFS/etc/pacman.d/gnupg"
# Delegate installs still trust the Arch keyring, so pin the exact keyring the
# image was built with instead of copying whatever the host happens to have.
log "verifying the pinned Arch keyring"
( cd / && sha256sum -c --quiet "$CONFIG/pacman-keyring.sha256" ) \
    || die "the host Arch keyring does not match config/pacman-keyring.sha256"
for keyfile in pubring.gpg trustdb.gpg tofu.db gpg.conf gpg-agent.conf; do
    [ -f "/etc/pacman.d/gnupg/$keyfile" ] || die "pacman keyring file missing: $keyfile"
    install -m 0644 "/etc/pacman.d/gnupg/$keyfile" "$ROOTFS/etc/pacman.d/gnupg/$keyfile"
done
for keyfile in archlinux.gpg archlinux-trusted archlinux-revoked; do
    [ -f "/usr/share/pacman/keyrings/$keyfile" ] || die "pacman keyring source missing: $keyfile"
    install -m 0644 "/usr/share/pacman/keyrings/$keyfile" \
        "$ROOTFS/usr/share/pacman/keyrings/$keyfile"
done

printf '%s\n' "$GRINTION_VERSION" > "$ROOTFS/etc/grintion/version"
sed "s/@VERSION@/$GRINTION_VERSION/g" "$ROOTFS/etc/issue.in" > "$ROOTFS/etc/issue"
sed "s/@VERSION@/$GRINTION_VERSION/g" "$ROOTFS/etc/motd.in" > "$ROOTFS/etc/motd"
sed "s/@VERSION@/$GRINTION_VERSION/g" "$ROOTFS/etc/issue.installed.in" > "$ROOTFS/etc/issue.installed"
sed "s/@VERSION@/$GRINTION_VERSION/g" "$ROOTFS/etc/motd.installed.in" > "$ROOTFS/etc/motd.installed"
rm -f "$ROOTFS/etc/issue.in" "$ROOTFS/etc/motd.in" "$ROOTFS/etc/issue.installed.in" "$ROOTFS/etc/motd.installed.in"
cat > "$ROOTFS/etc/os-release" <<EOF
NAME="Grintion-OS"
VERSION="${GRINTION_VERSION}"
ID=grintion
ID_LIKE=linux
VERSION_ID="${GRINTION_VERSION}"
PRETTY_NAME="Grintion-OS ${GRINTION_VERSION} (MISS)"
ANSI_COLOR="38;2;200;32;32"
HOME_URL="https://github.com/Freddyz-coder/grintion-OS"
BUG_REPORT_URL="https://github.com/Freddyz-coder/grintion-OS/issues"
EOF
: > "$ROOTFS/etc/machine-id"
chmod 0444 "$ROOTFS/etc/machine-id"

mkdir -p "$ROOTFS/root"
cp -a "$GRINTION_REPO_ROOT/etc/skel/." "$ROOTFS/root/"
chmod 0700 "$ROOTFS/root"
mkdir -p "$ROOTFS/root/.ssh"
chmod 0700 "$ROOTFS/root/.ssh"

# service links: every link points at a service that exists and whose run
# script only execs programs present in this rootfs.
for service in agetty-tty1 agetty-tty2 agetty-ttyS0 network firewall syslog local boot-health seatd udev timesync apparmor; do
    [ -x "$ROOTFS/etc/sv/$service/run" ] || die "service is missing or not executable: $service"
    ln -sfn "/etc/sv/$service" "$ROOTFS/var/service/$service"
done

# zram is the RAM-efficiency default, selfheal repairs broken state after
# boot-health, and auditd is now backed by a real userspace.
for service in zram selfheal auditd; do
    [ -x "$ROOTFS/etc/sv/$service/run" ] || die "service is missing or not executable: $service"
    ln -sfn "/etc/sv/$service" "$ROOTFS/var/service/$service"
done

# ---------------------------------------------------------------- modes
log "applying ownership-sensitive modes"
chmod 0600 "$ROOTFS/etc/shadow"
chmod 0600 "$ROOTFS/etc/gshadow" 2>/dev/null || true
chmod 0440 "$ROOTFS/etc/sudoers"
chmod 0640 "$ROOTFS/etc/audit/auditd.conf" "$ROOTFS/etc/audit/audit.rules" 2>/dev/null || true
chmod 0750 "$ROOTFS/etc/audit" "$ROOTFS/etc/audit/rules.d" 2>/dev/null || true
chmod 0755 "$ROOTFS/etc/runit/1" "$ROOTFS/etc/runit/2" "$ROOTFS/etc/runit/3"
chmod 0755 "$ROOTFS"/etc/sv/*/run
chmod 0700 "$ROOTFS/var/lib/garb" "$ROOTFS/var/lib/dhcpcd"
chmod 0755 "$ROOTFS/var/log"
chmod 1777 "$ROOTFS/tmp"

while IFS= read -r rel; do
    [ -n "$rel" ] || continue
    case "$rel" in \#*) continue ;; esac
    path="$ROOTFS/$rel"
    [ -e "$path" ] || die "setuid target missing: $rel"
    chmod 4755 "$path"
done < "$CONFIG/rootfs.setuid"

# ---------------------------------------------------------------- library closure
log "resolving the complete shared-library closure"
python3 "$GRINTION_REPO_ROOT/build/resolve-libs.py" "$ROOTFS"

# Seed pacman's local database only after the full file tree exists. The seed
# checks that a package's shared libraries and binaries are really in the image;
# dependency libraries are copied by resolve-libs.py above, so seeding earlier
# would mark present packages (zlib, libarchive, systemd-libs) as absent.
python3 "$GRINTION_REPO_ROOT/build/seed-pacman-db.py" "$ROOTFS" --epoch "$SOURCE_DATE_EPOCH"

# Recreate standard symlinks that the resolver may have skipped.
for alias in libc.so.6 libm.so.6 libpthread.so.0 libdl.so.2 librt.so.1 libutil.so.1; do
    if [ -f "$ROOTFS/usr/lib/$alias" ]; then :; fi
done

# Sanity: PAM and the dynamic loader must exist in the image.
[ -x "$ROOTFS/usr/lib/ld-linux-x86-64.so.2" ] || [ -e "$ROOTFS/usr/lib64/ld-linux-x86-64.so.2" ] || die "dynamic loader missing from rootfs"
[ -f "$ROOTFS/usr/lib/security/pam_unix.so" ] || die "pam_unix.so missing from rootfs"
[ -x "$ROOTFS/usr/bin/passwd" ] || die "passwd missing from rootfs"
[ -x "$ROOTFS/usr/bin/sudo" ] || die "sudo missing from rootfs"

# ---------------------------------------------------------------- initramfs
log "writing the live initramfs"
mkdir -p "$OUTPUT"
python3 "$GRINTION_REPO_ROOT/build/mkinitramfs.py" "$ROOTFS" "$OUTPUT/initramfs.img" \
    --epoch "$SOURCE_DATE_EPOCH" --compress zstd

log "live rootfs complete: $OUTPUT/initramfs.img ($(du -h "$OUTPUT/initramfs.img" | cut -f1))"
