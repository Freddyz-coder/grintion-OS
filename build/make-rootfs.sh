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

need_cmd bash
need_cmd python3
need_cmd cp
need_cmd install
need_cmd ldd
need_cmd cpio
need_cmd gzip
need_cmd sha256sum

log "assembling live rootfs for Grintion-OS $GRINTION_VERSION ($KREL)"

# ---------------------------------------------------------------- directories
rm -rf "$ROOTFS"
mkdir -p "$ROOTFS"/usr/{bin,sbin,lib,lib64,share,include,libexec} \
         "$ROOTFS"/{etc,var,run,proc,sys,dev,tmp,root,home,mnt,media,srv,opt,boot}
mkdir -p "$ROOTFS"/var/{log,spool/mail,lib/garb,lib/dhcpcd,cache/garb}
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
for tool in garb grintion-install grintion-persist grintion-chroot limine-deploy live-shell; do
    [ -f "$GRINTION_REPO_ROOT/bin/$tool" ] || die "missing repository tool: bin/$tool"
    install -D -m 0755 "$GRINTION_REPO_ROOT/bin/$tool" "$ROOTFS/usr/bin/$tool"
done
install -D -m 0755 "$GRINTION_REPO_ROOT/init/live-init" "$ROOTFS/init"

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
if [ -d /usr/lib/ossl-modules ]; then
    mkdir -p "$ROOTFS/usr/lib/ossl-modules"
    cp -a /usr/lib/ossl-modules/. "$ROOTFS/usr/lib/ossl-modules/"
fi
if [ -f /usr/share/zoneinfo/UTC ]; then
    install -D -m 0644 /usr/share/zoneinfo/UTC "$ROOTFS/usr/share/zoneinfo/UTC"
    ln -sfn /usr/share/zoneinfo/UTC "$ROOTFS/etc/localtime"
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

for asset in limine limine-bios.sys limine-bios-cd.bin limine-uefi-cd.bin BOOTX64.EFI BOOTAA64.EFI; do
    [ -f "$GRINTION_REPO_ROOT/tools/limine/$asset" ] || die "limine asset missing: $asset"
    install -D -m 0644 "$GRINTION_REPO_ROOT/tools/limine/$asset" "$ROOTFS/usr/share/limine/$asset"
done
chmod 0755 "$ROOTFS/usr/share/limine/limine"

# ---------------------------------------------------------------- configuration
log "deploying /etc configuration"
cp -a "$GRINTION_REPO_ROOT/etc/." "$ROOTFS/etc/"

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
for service in agetty-tty1 agetty-tty2 agetty-ttyS0 network firewall syslog local; do
    [ -x "$ROOTFS/etc/sv/$service/run" ] || die "service is missing or not executable: $service"
    ln -sfn "/etc/sv/$service" "$ROOTFS/var/service/$service"
done

# ---------------------------------------------------------------- modes
log "applying ownership-sensitive modes"
chmod 0600 "$ROOTFS/etc/shadow"
chmod 0600 "$ROOTFS/etc/gshadow" 2>/dev/null || true
chmod 0440 "$ROOTFS/etc/sudoers"
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
python3 "$GRINTION_REPO_ROOT/build/mkinitramfs.py" "$ROOTFS" "$OUTPUT/initramfs.img" --epoch "$SOURCE_DATE_EPOCH"

log "live rootfs complete: $OUTPUT/initramfs.img ($(du -h "$OUTPUT/initramfs.img" | cut -f1))"
