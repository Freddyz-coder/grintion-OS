# Grintion-OS build system
# Philosophy: MISS (Minimalist, Independent, Secure, Stable)

SHELL := /bin/bash
.SHELLFLAGS := -Eeuo pipefail -c
.DEFAULT_GOAL := help

VERSION := $(shell cat VERSION)
ISO := output/grintion-os-x86_64.iso

.PHONY: all help tools kernel install-initramfs rootfs iso check test test-garb \
        test-boot test-display test-network test-install test-install-uefi test-all packages clean distclean release \
        sign-release verify-release

all: iso

help:
	@echo "Grintion-OS $(VERSION) build system"
	@echo ""
	@echo "Targets:"
	@echo "  make tools             verify/rebuild the pinned build tools"
	@echo "  make kernel            build the pinned vanilla Linux kernel and modules"
	@echo "  make install-initramfs build the tiny installed-system initramfs"
	@echo "  make rootfs            assemble the live rootfs and live initramfs"
	@echo "  make iso               build output/grintion-os-x86_64.iso (default)"
	@echo "  make check             static checks, Python tests, package tests"
	@echo "  make test              alias for check"
	@echo "  make test-garb         package-manager integration tests"
	@echo "  make test-boot         boot the ISO in QEMU (BIOS + UEFI)"
	@echo "  make test-display      check the live ISO renders on the framebuffer"
	@echo "  make test-network      boot with e1000, e1000e, virtio-net, rtl8139 and pcnet"
	@echo "  make test-install      install to a QEMU disk and reboot from it"
	@echo "  make test-install-uefi install under UEFI/OVMF and reboot from it"
	@echo "  make test-all          check + boot tests + install test"
	@echo "  make packages          build the local demo repository"
	@echo "  make clean             remove build/work and generated output"
	@echo "  make distclean         also remove downloaded sources and caches"
	@echo "  make release           check, build the ISO and print checksums"
	@echo "  make sign-release      sign output/SHA256SUMS with GRINTION_RELEASE_KEY"
	@echo "  make verify-release    verify the checksum and detached signature"

tools:
	@./build/build-tools.sh

kernel: tools
	@./build/kernel.sh

install-initramfs:
	@./build/make-install-initramfs.sh

rootfs: tools kernel install-initramfs
	@./build/make-rootfs.sh

iso: tools kernel install-initramfs rootfs
	@./build/build-iso.sh

check:
	@./build/check.sh

test: check

test-garb: check
	@python3 -m pytest -q tests/test_garb.py

test-boot: iso
	@./build/test-boot.sh

test-display: iso
	@python3 tests/display_test.py --iso $(ISO)

test-network: iso
	@./build/test-network.sh

test-install: iso
	@./build/test-install.sh

test-install-uefi: iso
	@./build/test-install.sh --uefi

test-all: check test-boot test-install

packages:
	@./bin/garb repo-build packages output/packages
	@./bin/garb repo-index output/packages

clean:
	@echo ">> removing build/work and generated output"
	@rm -rf build/work output dist
	@echo "[+] clean"

distclean: clean
	@echo ">> removing downloaded sources and caches"
	@rm -rf build/cache
	@echo "[+] distclean"

release: check iso
	@echo ""
	@echo "Artifacts:"
	@ls -lh $(ISO) $(ISO).sha256 output/BUILD-INFO
	@echo ""
	@echo "Tag and publish with:"
	@echo "  git tag -a v$(VERSION) -m 'Grintion-OS $(VERSION)'"
	@echo "  git push origin main v$(VERSION)"
	@echo "  gh release create v$(VERSION) $(ISO) $(ISO).sha256 output/BUILD-INFO"

sign-release:
	@./build/sign-release.sh

verify-release:
	@./bin/grintion-release-verify $(ISO) --sha256-file output/SHA256SUMS \
	    $${GRINTION_RELEASE_PUBKEY:+--key "$$GRINTION_RELEASE_PUBKEY"} --require-signature
