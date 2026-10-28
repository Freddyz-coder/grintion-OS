#!/usr/bin/env bash
# make-rootfs.sh - Assembles independent RAM-live rootfs and initramfs
# Adheres to the MISS philosophy (Minimalist, Independent, Secure, Stable)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORK_DIR="${REPO_ROOT}/build/work"
ROOTFS="${WORK_DIR}/rootfs"
OUTPUT_DIR="${REPO_ROOT}/output"

echo "=============================================================="
echo ">> [1/5] Initializing Rootfs Directory Hierarchy..."
echo "=============================================================="
rm -rf "$ROOTFS"
mkdir -p "$ROOTFS"/{bin,sbin,usr/bin,usr/sbin,usr/lib,usr/lib64,lib,lib64,etc,var,run,proc,sys,dev,tmp,root,home,mnt,var/service,var/log,var/lib/garb,var/cache/garb}
chmod 1777 "$ROOTFS/tmp"
chmod 0700 "$ROOTFS/root"

echo "=============================================================="
echo ">> [2/5] Deploying System Binaries & Utilities..."
echo "=============================================================="

# Essential binaries for DIY install, networking, partitioning, and garb
BINARIES=(
    "bash" "sh" "ls" "cat" "cp" "mv" "rm" "mkdir" "rmdir" "chmod" "chown"
    "dd" "sync" "uname" "date" "id" "env" "sleep" "touch" "head" "tail"
    "grep" "sed" "awk" "find" "tar" "gzip" "mount" "umount" "ip"
    "fdisk" "parted" "mkfs.ext4" "mkfs.vfat" "agetty" "login" "python3"
)

# Collect full paths of available binaries
BIN_PATHS=()
for b in "${BINARIES[@]}"; do
    bin_loc="$(which "$b" 2>/dev/null || true)"
    if [ -n "$bin_loc" ]; then
        BIN_PATHS+=("$bin_loc")
        cp -L "$bin_loc" "$ROOTFS/usr/bin/"
    fi
done

# Ensure sh points to bash
if [ ! -e "$ROOTFS/usr/bin/sh" ]; then
    ln -s bash "$ROOTFS/usr/bin/sh"
fi

# Create traditional /bin and /sbin symlinks or binaries
for b in bash sh ls cat cp mv rm mkdir rmdir chmod chown dd sync uname date id env sleep touch head tail grep sed awk find tar gzip mount umount ip fdisk; do
    if [ -f "$ROOTFS/usr/bin/$b" ]; then
        ln -sf "../usr/bin/$b" "$ROOTFS/bin/$b"
    fi
done

# Copy runit binaries
if [ -f "$REPO_ROOT/tools/bin/runit" ]; then
    cp "$REPO_ROOT/tools/bin/"{runit,runsv,runsvdir,sv,chpst} "$ROOTFS/usr/sbin/"
    for r in runit runsv runsvdir sv chpst; do
        ln -sf "../usr/sbin/$r" "$ROOTFS/sbin/$r"
    done
fi

# Deploy garb and DIY utilities
cp "$REPO_ROOT/bin/garb" "$ROOTFS/usr/bin/garb"
cp "$REPO_ROOT/bin/diy-guide" "$ROOTFS/usr/bin/diy-guide"
cp "$REPO_ROOT/bin/grintion-install" "$ROOTFS/usr/bin/grintion-install"
cp "$REPO_ROOT/bin/grintion-chroot" "$ROOTFS/usr/bin/grintion-chroot"
cp "$REPO_ROOT/bin/limine-deploy" "$ROOTFS/usr/bin/limine-deploy"
chmod +x "$ROOTFS/usr/bin/"{garb,diy-guide,grintion-install,grintion-chroot,limine-deploy}

for u in garb diy-guide grintion-install grintion-chroot limine-deploy; do
    ln -sf "../usr/bin/$u" "$ROOTFS/bin/$u"
done

echo "=============================================================="
echo ">> [3/5] Resolving and Copying Shared Dynamic Libraries..."
echo "=============================================================="

# Use python to resolve all dependent .so files recursively
export ROOTFS
python3 - << 'EOF'
import os
import sys
import subprocess
import shutil

rootfs = os.environ.get("ROOTFS")
bin_dir = os.path.join(rootfs, "usr/bin")
sbin_dir = os.path.join(rootfs, "usr/sbin")
lib_dir = os.path.join(rootfs, "usr/lib")
lib64_dir = os.path.join(rootfs, "usr/lib64")

binaries = []
for d in [bin_dir, sbin_dir]:
    if os.path.exists(d):
        for f in os.listdir(d):
            p = os.path.join(d, f)
            if os.path.isfile(p) and not os.path.islink(p):
                binaries.append(p)

libs_to_copy = set()
visited = set()

def scan_file(f):
    if f in visited or not os.path.exists(f):
        return
    visited.add(f)
    try:
        res = subprocess.run(["ldd", f], capture_output=True, text=True)
        for line in res.stdout.splitlines():
            line = line.strip()
            if "=>" in line:
                dest = line.split("=>")[1].strip().split()[0]
                if dest.startswith("/"):
                    libs_to_copy.add(dest)
                    scan_file(dest)
            elif line.startswith("/lib"):
                dest = line.split()[0]
                libs_to_copy.add(dest)
                scan_file(dest)
    except Exception:
        pass

for b in binaries:
    scan_file(b)

print(f"Total libraries resolved: {len(libs_to_copy)}")
for lib in libs_to_copy:
    base = os.path.basename(lib)
    target = os.path.join(lib_dir, base)
    if not os.path.exists(target):
        try:
            shutil.copy2(lib, target)
        except Exception as e:
            print(f"Warning copying {lib}: {e}")

    # Ensure dynamic linker is accessible
    if "ld-linux" in base:
        shutil.copy2(lib, os.path.join(rootfs, "lib64", base))
        # Symlink /lib/ld-linux-x86-64.so.2 -> /lib64/ld-linux-x86-64.so.2
        l64 = os.path.join(rootfs, "lib", base)
        if not os.path.exists(l64):
            shutil.copy2(lib, l64)
EOF

# Ensure /lib and /lib64 symlinks exist
(cd "$ROOTFS" && ln -sf usr/lib/* lib/ 2>/dev/null || true)
(cd "$ROOTFS" && ln -sf usr/lib/* lib64/ 2>/dev/null || true)

# Copy minimal Python 3 standard library
PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
HOST_PY_DIR="/usr/lib/python${PY_VER}"
TARGET_PY_DIR="$ROOTFS/usr/lib/python${PY_VER}"

if [ -d "$HOST_PY_DIR" ]; then
    echo "[*] Copying core Python ${PY_VER} modules..."
    mkdir -p "$TARGET_PY_DIR"
    # Copy essential python modules required by garb
    for mod in os.py sys.py posixpath.py genericpath.py stat.py \
               hashlib.py json tarfile.py shutil.py subprocess.py \
               argparse.py time.py pathlib.py io.py codecs.py \
               encodings abc.py types.py functools.py re collections \
               urllib logging copy.py copyreg.py contextlib.py; do
        if [ -e "$HOST_PY_DIR/$mod" ]; then
            cp -r "$HOST_PY_DIR/$mod" "$TARGET_PY_DIR/" 2>/dev/null || true
        fi
    done
fi

echo "=============================================================="
echo ">> [4/5] Deploying System Configuration & Init Services..."
echo "=============================================================="

# Copy etc configuration files
cp -r "$REPO_ROOT/etc/"* "$ROOTFS/etc/"
chmod 0644 "$ROOTFS/etc/passwd" "$ROOTFS/etc/group"
chmod 0600 "$ROOTFS/etc/shadow"

# Set up runit service links
mkdir -p "$ROOTFS/var/service"
ln -sf /etc/sv/agetty-tty1 "$ROOTFS/var/service/agetty-tty1"

# Create /init script for initramfs
cat << 'EOF' > "$ROOTFS/init"
#!/bin/sh
# /init - Grintion-OS Live RAM Environment Init
PATH=/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin
export PATH

# Mount core pseudo-filesystems
mount -t proc proc /proc -o nosuid,noexec,nodev
mount -t sysfs sys /sys -o nosuid,noexec,nodev
mount -t devtmpfs dev /dev -o mode=0755,nosuid
mkdir -p /dev/pts /dev/shm
mount -t devpts devpts /dev/pts -o mode=0620,gid=5,nosuid,noexec
mount -t tmpfs shm /dev/shm -o mode=1777,nosuid,nodev
mkdir -p /sys/fs/cgroup
mount -t cgroup2 none /sys/fs/cgroup -o nsdelegate 2>/dev/null || true

# Hostname
hostname grintion-live

# Loopback interface
ip link set up dev lo 2>/dev/null || true

# Apply paranoid sysctl security lockdown
for f in /etc/sysctl.d/*.conf; do
    [ -f "$f" ] && sysctl -p "$f" >/dev/null 2>&1
done

# Seed random generator
if [ -c /dev/urandom ]; then
    dd if=/dev/urandom of=/dev/null count=1 bs=32 2>/dev/null || true
fi

# Print login banner with ASCII logo
cat /etc/issue

# Start runit supervision if present, else fallback to bash shell
if [ -x /sbin/runit ]; then
    echo ">> Launching runit process supervisor..."
    exec /sbin/runit
else
    echo ">> Launching Grintion Live shell..."
    while true; do
        /bin/bash --login
    done
fi
EOF
chmod +x "$ROOTFS/init"

echo "=============================================================="
echo ">> [5/5] Compressing Rootfs into Bootable Initramfs..."
echo "=============================================================="
mkdir -p "$OUTPUT_DIR"
(cd "$ROOTFS" && find . -print0 | cpio --null -ov --format=newc | gzip -9 > "$OUTPUT_DIR/initramfs.img")

echo "[+] Initramfs built successfully: $OUTPUT_DIR/initramfs.img ($(du -h "$OUTPUT_DIR/initramfs.img" | cut -f1))"
