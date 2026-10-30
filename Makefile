# Grintion-OS Master Makefile
# Philosophy: MISS (Minimalist, Independent, Secure, Stable)

.PHONY: all iso rootfs packages clean help test

all: iso

help:
	@echo "Grintion-OS Build System (MISS Philosophy)"
	@echo "Targets:"
	@echo "  make iso       - Assemble rootfs and generate bootable hybrid .ISO"
	@echo "  make rootfs    - Generate independent RAM-live rootfs and initramfs"
	@echo "  make packages  - Build core .garb packages from manifests"
	@echo "  make test      - Run garb CLI and package manager validation tests"
	@echo "  make clean     - Clean intermediate build artifacts"

packages:
	@echo ">> Building base .garb packages..."
	@mkdir -p dist
	@./bin/garb build packages/base-files/Garbfile -o dist
	@./bin/garb build packages/linux/Garbfile -o dist
	@./bin/garb build packages/runit/Garbfile -o dist
	@./bin/garb build packages/gnu-coreutils/Garbfile -o dist
	@./bin/garb build packages/garb/Garbfile -o dist

rootfs:
	@echo ">> Assembling rootfs and initramfs..."
	@./build/make-rootfs.sh

iso: rootfs
	@echo ">> Building Grintion-OS Bootable Hybrid ISO..."
	@./build/build-iso.sh

test:
	@echo ">> Validating garb package manager..."
	@./bin/garb version
	@./bin/garb search base
	@./bin/garb info base-files
	@echo ">> Validating init scripts syntax..."
	@sh -n etc/runit/1
	@sh -n etc/runit/2
	@sh -n etc/runit/3
	@sh -n bin/grintion-install
	@sh -n bin/grintion-persist
	@sh -n bin/grintion-chroot
	@sh -n bin/limine-deploy
	@echo "[+] All validation tests PASSED!"

clean:
	@echo ">> Cleaning build directory..."
	@rm -rf build/work
	@echo "[+] Clean complete."
