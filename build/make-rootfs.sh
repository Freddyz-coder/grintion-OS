#!/usr/bin/env bash
# make-rootfs.sh - Assembles independent RAM-live rootfs and initramfs
# Adheres to the MISS philosophy (Minimalist, Independent, Secure, Stable)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORK_DIR="${REPO_ROOT}/build/work"
ROOTFS="${WORK_DIR}/rootfs"
OUTPUT_DIR="${REPO_ROOT}/output"
export ROOTFS
export OUTPUT_DIR

echo "=============================================================="
echo ">> [1/5] Initializing Rootfs Directory Hierarchy..."
echo "=============================================================="
rm -rf "$ROOTFS"
mkdir -p "$ROOTFS"/{usr/bin,usr/sbin,usr/lib,etc,var,run,proc,sys,dev,tmp,root,home,mnt,var/service,var/log,var/lib/garb,var/cache/garb}
chmod 1777 "$ROOTFS/tmp"
chmod 0700 "$ROOTFS/root"

# Create standard merged-usr symlinks (relative symlinks pointing to usr)
ln -sf usr/bin "$ROOTFS/bin"
ln -sf usr/sbin "$ROOTFS/sbin"
ln -sf usr/lib "$ROOTFS/lib"
ln -sf usr/lib "$ROOTFS/lib64"
ln -sf lib "$ROOTFS/usr/lib64"

echo "=============================================================="
echo ">> [2/5] Deploying System Binaries & Utilities..."
echo "=============================================================="

# Essential binaries for DIY install, networking, partitioning, and garb
BINARIES=(
    # Shell
    "bash" "sh"
    # GNU coreutils
    "ls" "cat" "cp" "mv" "rm" "mkdir" "rmdir" "chmod" "chown"
    "dd" "sync" "uname" "date" "id" "env" "sleep" "touch" "head" "tail"
    "ln" "stat" "wc" "sort" "uniq" "tr" "cut" "tee" "xargs"
    "file" "which" "diff" "dirname" "basename" "readlink" "realpath"
    "mknod" "mktemp" "yes" "true" "false" "echo" "printf" "test"
    # Text processing
    "grep" "sed" "awk" "find"
    # Archiving
    "tar" "gzip" "bzip2" "xz" "unzip" "cpio"
    # Filesystem
    "mount" "umount" "fdisk" "parted" "mkfs.ext4" "mkfs.vfat"
    "blkid" "findfs" "losetup" "lsblk" "df" "du"
    # Process & system monitoring
    "ps" "top" "htop" "kill" "killall" "free" "dmesg" "uptime"
    # Kernel modules
    "lsmod" "modprobe" "insmod" "rmmod" "depmod" "modinfo"
    # Hardware info
    "lspci" "lsusb"
    # User management
    "passwd" "useradd" "userdel" "groupadd" "groupdel" "su" "sudo" "chpasswd" "login"
    # Editors & pagers
    "nano" "vi" "less" "more"
    # Networking
    "ip" "dhcpcd" "wpa_supplicant" "wpa_cli" "ping" "wget" "curl"
    "iw" "rfkill" "ss" "nslookup" "dig"
    # System control
    "hostname" "reboot" "poweroff" "halt" "shutdown"
    "sysctl" "chroot" "pivot_root" "agetty"
    # Misc
    "python3" "fastfetch"
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

# Copy runit binaries
if [ -f "$REPO_ROOT/tools/bin/runit" ]; then
    cp "$REPO_ROOT/tools/bin/"{runit,runsv,runsvdir,sv,chpst} "$ROOTFS/usr/sbin/"
fi

# Deploy garb and system utilities
cp "$REPO_ROOT/bin/garb" "$ROOTFS/usr/bin/garb"
cp "$REPO_ROOT/bin/grintion-install" "$ROOTFS/usr/bin/grintion-install"
cp "$REPO_ROOT/bin/grintion-persist" "$ROOTFS/usr/bin/grintion-persist"
cp "$REPO_ROOT/bin/grintion-chroot" "$ROOTFS/usr/bin/grintion-chroot"
cp "$REPO_ROOT/bin/limine-deploy" "$ROOTFS/usr/bin/limine-deploy"
chmod +x "$ROOTFS/usr/bin/"{garb,grintion-install,grintion-persist,grintion-chroot,limine-deploy}

# Ensure sh points to bash
ln -sf bash "$ROOTFS/usr/bin/sh"

# Deploy default DNS resolver configuration
cat << 'RESOLV' > "$ROOTFS/etc/resolv.conf"
# Grintion-OS default DNS (Cloudflare + Google fallback)
nameserver 1.1.1.1
nameserver 8.8.8.8
RESOLV

# WiFi configuration directory
mkdir -p "$ROOTFS/etc/wpa_supplicant"

# Copy clean Python 3 standard library first
PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
HOST_PY_DIR="/usr/lib/python${PY_VER}"
TARGET_PY_DIR="$ROOTFS/usr/lib/python${PY_VER}"

if [ -d "$HOST_PY_DIR" ]; then
    echo "[*] Deploying clean Python ${PY_VER} standard library..."
    python3 - << 'PYCOPY'
import os
import shutil
rootfs = os.environ.get("ROOTFS")
py_ver = os.popen('python3 -c "import sys; print(f\'{sys.version_info.major}.{sys.version_info.minor}\')"').read().strip()
src = f"/usr/lib/python{py_ver}"
dest = f"{rootfs}/usr/lib/python{py_ver}"
if os.path.exists(dest):
    shutil.rmtree(dest)

def ignore_filter(s, names):
    return [n for n in names if n in ('site-packages', 'test', 'tests', '__pycache__', 'idlelib', 'tkinter', 'turtledemo')]

shutil.copytree(src, dest, ignore=ignore_filter, symlinks=True)
print(f"Copied clean python stdlib to {dest}")
PYCOPY
fi

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
import glob

rootfs = os.environ.get("ROOTFS")
bin_dir = os.path.join(rootfs, "usr/bin")
sbin_dir = os.path.join(rootfs, "usr/sbin")
lib_dir = os.path.join(rootfs, "usr/lib")

binaries = []
for d in [bin_dir, sbin_dir]:
    if os.path.exists(d):
        for f in os.listdir(d):
            p = os.path.join(d, f)
            if os.path.isfile(p) and not os.path.islink(p):
                binaries.append(p)

# Also scan all python C extension shared objects
for so in glob.glob(f"{rootfs}/usr/lib/python*/**/*.so", recursive=True):
    binaries.append(so)

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
            elif line.startswith("/lib") or line.startswith("/usr/lib"):
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
EOF

echo "=============================================================="
echo ">> [3.5/5] Deploying Kernel Module Infrastructure..."
echo "=============================================================="
KVER=$(uname -r)
HOST_MOD_DIR="/lib/modules/$KVER"
TARGET_MOD_DIR="$ROOTFS/lib/modules/$KVER"

if [ -d "$HOST_MOD_DIR" ]; then
    echo "[*] Deploying essential kernel modules from $HOST_MOD_DIR..."
    mkdir -p "$TARGET_MOD_DIR"

    # Copy essential module categories (not the entire tree)
    for category in kernel/drivers/net kernel/drivers/gpu kernel/drivers/usb \
                    kernel/drivers/hid kernel/drivers/input kernel/drivers/block \
                    kernel/drivers/nvme kernel/drivers/ata kernel/drivers/scsi \
                    kernel/fs kernel/sound; do
        if [ -d "$HOST_MOD_DIR/$category" ]; then
            mkdir -p "$TARGET_MOD_DIR/$category"
            cp -r "$HOST_MOD_DIR/$category"/* "$TARGET_MOD_DIR/$category/" 2>/dev/null || true
        fi
    done

    # Copy module metadata files
    for f in modules.dep modules.dep.bin modules.alias modules.alias.bin \
             modules.symbols modules.symbols.bin modules.builtin \
             modules.builtin.bin modules.order; do
        [ -f "$HOST_MOD_DIR/$f" ] && cp "$HOST_MOD_DIR/$f" "$TARGET_MOD_DIR/" 2>/dev/null || true
    done
    echo "[+] Kernel modules deployed for $KVER"
else
    echo "[!] No kernel modules found at $HOST_MOD_DIR (skipping)"
fi

echo "=============================================================="
echo ">> [4/5] Deploying System Configuration & Init Services..."
echo "=============================================================="

# Copy etc configuration files
cp -r "$REPO_ROOT/etc/"* "$ROOTFS/etc/"
chmod 0644 "$ROOTFS/etc/passwd" "$ROOTFS/etc/group"
chmod 0600 "$ROOTFS/etc/shadow"

# Deploy fastfetch configuration and logo
mkdir -p "$ROOTFS/etc/fastfetch"
cp "$REPO_ROOT/etc/fastfetch/config.jsonc" "$ROOTFS/etc/fastfetch/" 2>/dev/null || true
cp "$REPO_ROOT/etc/grintion-logo.txt" "$ROOTFS/etc/" 2>/dev/null || true

# Set up runit service links
mkdir -p "$ROOTFS/var/service"
ln -sf /etc/sv/agetty-tty1 "$ROOTFS/var/service/agetty-tty1"
ln -sf /etc/sv/network "$ROOTFS/var/service/network"

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

# Check for persistence partition (LABEL=GRINTION_PERSIST on SSD, HDD, or USB)
PERSIST_DEV="$(blkid -L GRINTION_PERSIST 2>/dev/null || true)"
if [ -n "$PERSIST_DEV" ]; then
    echo ">> [PERSISTENCE] Detected partition: $PERSIST_DEV (LABEL=GRINTION_PERSIST)"
    mkdir -p /mnt/persist
    if mount "$PERSIST_DEV" /mnt/persist 2>/dev/null; then
        echo ">> [PERSISTENCE] Enabling persistent overlays..."
        mkdir -p /mnt/persist/etc_upper /mnt/persist/etc_work
        mkdir -p /mnt/persist/home /mnt/persist/root /mnt/persist/var_lib_garb

        # Overlay /etc (configuration changes, passwords, services)
        mount -t overlay overlay -o lowerdir=/etc,upperdir=/mnt/persist/etc_upper,workdir=/mnt/persist/etc_work /etc 2>/dev/null || true

        # Bind-mount user directories and package store
        mount --bind /mnt/persist/home /home 2>/dev/null || true
        mount --bind /mnt/persist/root /root 2>/dev/null || true
        mount --bind /mnt/persist/var_lib_garb /var/lib/garb 2>/dev/null || true

        echo ">> [PERSISTENCE] Persistent storage ACTIVE for /etc, /home, /root, /var/lib/garb"
    fi
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
