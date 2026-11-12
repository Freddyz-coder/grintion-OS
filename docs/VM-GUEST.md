# Running Grintion-OS in a virtual machine

This page covers the two host-side settings that most often look like guest
bugs: pointer alignment and missing audio. The guest cannot fix a host that
does not expose the right virtual hardware.

## Pointer alignment

Grintion-OS runs standalone `systemd-udevd` and uses libinput for XFCE/KDE.
QEMU/libvirt/VirtualBox can still expose both a relative PS/2 mouse and an
absolute USB tablet. The display-manager service now runs
`grintion-pointer-sync` before Xorg/KWin: when an absolute tablet is present,
the relative duplicate is marked with libinput's `LIBINPUT_IGNORE_DEVICE`
property. Only the absolute device drives the cursor. If no tablet is present,
the relative mouse is left enabled.

### QEMU

Use an absolute pointing device:

```sh
qemu-system-x86_64 ... -usb -device usb-tablet
```

Without `usb-tablet`, QEMU's default PS/2 mouse is relative. Its acceleration
and the host window's scaling can make the guest cursor drift away from the
host cursor. Expose the tablet and let Grintion ignore the emulated relative
mouse:

```sh
qemu-system-x86_64 ... -usb -device usb-tablet
```

After changing the input devices, restart the display manager (`sudo sv
restart display-manager`) or reboot. Check the rule with:

```sh
sudo grintion-pointer-sync --dry-run
cat /run/udev/rules.d/99-grintion-pointer-sync.rules
```

The QEMU/KVM test probe uses `usb-tablet` and an absolute QMP pointer event;
that path moved the guest cursor to the requested coordinate.

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
provide the pointer integration and display resize support. The same
`grintion-pointer-sync` rule suppresses a duplicate relative device when the
absolute tablet is visible.

## Audio

The 0.10.0 kernel has the HDA controller, HDA codec parsers and USB audio built
in. The desktop profiles install `pipewire`, `pipewire-pulse`, `pipewire-alsa`,
`wireplumber`, `alsa-ucm-conf`, `sof-firmware`, `linux-firmware` and
`alsa-utils`. The shared `grintion-audio` helper starts PipeWire, WirePlumber
and the PulseAudio compatibility daemon because this image has no systemd user
manager to activate their sockets. It is called by the X11 hook and by an XDG
autostart entry, and it unmutes every detected ALSA card. PipeWire enumerates
real sinks through udev; there is no hard-coded `plughw:0,0` sink.

If an older installation has no sound, reinstall the desktop profile to pull
the audio packages, firmware and session helper:

```sh
sudo grintion-desktop install xfce   # or i3, kde, lxqt, sway
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

On QEMU, the guest only has a sound card if the host creates one. For playback
capture to a WAV file, use an output-only HDA codec:

```sh
qemu-system-x86_64 ... \
    -audiodev wav,id=snd0,path=guest-audio.wav \
    -device intel-hda \
    -device hda-output,audiodev=snd0
```

`hda-duplex` opens a capture stream as well. QEMU's WAV backend is
playback-only and logs `audio: Can not open 'adc' (no host audio driver)`, so
use `hda-output` for WAV capture. For interactive host audio, a duplex codec
with a real backend works:

```sh
qemu-system-x86_64 ... \
    -audiodev pa,id=snd0 \
    -device intel-hda \
    -device hda-duplex,audiodev=snd0
```

Use `-audiodev none` for a silent but functional guest. A VM created without
an audio device shows no card in `/proc/asound/cards`, regardless of PipeWire.

The release probe uses QEMU's `wav` backend and verifies that a 440 Hz tone
played through the native PipeWire client (`pw-play`) and through direct ALSA
(`aplay -D plughw:0,0`) produces non-silent samples. It does not test a
physical host speaker. PipeWire 1.6.11 is the current Arch stable version and
includes the fix for the 1.6.10 `pipewire-alsa` drain lockup. On an older
1.6.10 image, use `pw-play`, direct `plughw` playback, or upgrade the package.
