# Running Grintion-OS in a virtual machine

This page covers the two host-side settings that most often look like guest
bugs: pointer alignment and missing audio. The guest cannot fix a host that
does not expose the right virtual hardware.

## Pointer alignment

Grintion-OS uses the kernel's evdev devices directly because the image has no
udev. A relative PS/2 mouse and an absolute USB tablet are therefore two
different input devices.

### QEMU

Use an absolute pointing device:

```sh
qemu-system-x86_64 ... -usb -device usb-tablet
```

Without `usb-tablet`, QEMU's default PS/2 mouse is relative. Its acceleration
and the host window's scaling can make the guest cursor drift away from the
host cursor. The QEMU/KVM test probe uses `usb-tablet` and an absolute QMP
pointer event; that path moved the guest cursor to the requested coordinate.

If the QEMU window is scaled, turn off the viewer's zoom-to-fit/scale option or
run it at 1:1. The guest receives coordinates for its own framebuffer; a scaled
window is a host-side display transform.

For a SPICE display, install `spice-vdagent` in the guest and enable the SPICE
agent channel. For libvirt/virt-manager, add a USB Tablet input device to the
VM rather than relying on the emulated PS/2 mouse.

### VirtualBox

Set **Settings → System → Pointing Device** to **USB Tablet**. The default
PS/2 mouse is relative and will not track the host pointer reliably. The
VirtualBox GPU profile installs `virtualbox-guest-utils`; the guest additions
provide the pointer integration and display resize support.

## Audio

The 0.8.5 kernel has the HDA controller, HDA codec parsers and USB audio built
in. The desktop profiles install `pipewire`, `pipewire-pulse`, `pipewire-alsa`,
`wireplumber`, `alsa-ucm-conf`, `sof-firmware` and `alsa-utils`. The X11 session
hook starts PipeWire, WirePlumber and the PulseAudio compatibility daemon
because this image has no systemd user manager to activate their sockets.

If an older 0.8.4 installation has no sound, reinstall the desktop profile to
pull the audio packages and session hook from 0.8.5:

```sh
sudo grintion-desktop install xfce   # or gnome, kde, lxqt, i3, sway
```

Diagnose inside the guest:

```sh
cat /proc/asound/cards       # the HDA/USB card must be listed
aplay -l                     # ALSA playback devices
pgrep -a -x pipewire
pgrep -a -x wireplumber
pgrep -a -x pipewire-pulse
wpctl status                 # sinks and default device
```

On QEMU, the guest only has a sound card if the host creates one. For example:

```sh
qemu-system-x86_64 ... \
    -audiodev pa,id=snd0 \
    -device intel-hda \
    -device hda-duplex,audiodev=snd0
```

Use `-audiodev none` for a silent but functional guest, or `-audiodev wav` to
capture the guest output to a file. A VM created without an audio device will
show no card in `/proc/asound/cards`, regardless of PipeWire.

The release probe uses QEMU's `wav` audio backend and verifies that a 440 Hz
tone played through PipeWire produces non-silent samples. It does not test a
physical host speaker.
