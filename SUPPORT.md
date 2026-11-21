# Support

Grintion-OS support is community-based and best effort. There is no service
level agreement, no paid support contract and no guaranteed response time.
Security fixes are handled as described in [SECURITY.md](SECURITY.md).

Funding and donation channels are documented in
[docs/SUPPORT-AND-FUNDING.md](docs/SUPPORT-AND-FUNDING.md).

## Where to ask

| I need to... | Go to |
| --- | --- |
| Ask a question, share a setup, discuss hardware | [Discussions](https://github.com/Freddyz-coder/grintion-OS/discussions) |
| Report a reproducible bug | [Bug report](https://github.com/Freddyz-coder/grintion-OS/issues/new?template=bug_report.md) |
| Request a feature | [Feature request](https://github.com/Freddyz-coder/grintion-OS/issues/new?template=feature_request.md) |
| Report a vulnerability | [Private security advisory](https://github.com/Freddyz-coder/grintion-OS/security/advisories/new) |
| Install or recover a system | [docs/INSTALL.md](docs/INSTALL.md), [docs/RECOVERY.md](docs/RECOVERY.md) |
| Understand a command or error code | `grintion-help --list`, [docs/COMMANDS.md](docs/COMMANDS.md) |

Do not open a public issue for an unfixed vulnerability. Do not paste private
keys, LUKS passphrases, Wi-Fi credentials or full `dmesg` output that contains
serial numbers you do not want published.

## What to include in a report

- The version: `cat /etc/grintion/version`, and the architecture.
- Whether the problem is on the live image, an installed system, the installer,
  `garb`, or a desktop profile.
- The exact command and its full output, not a summary of it.
- For boot or hardware problems: the firmware mode (BIOS or UEFI), the machine
  model, and whether it also fails in QEMU.
- The sanitized bundle from `grintion-report`, which collects the system state
  without secrets.

If a test or a claim was not verified on your hardware, say so. The project
prefers an honest "not tested" over an assumed pass; see
[CONTRIBUTING.md](CONTRIBUTING.md).

## What support is not

- There is no telephone, chat or private consulting channel.
- A bug report is not a promise that the bug will be fixed.
- Requests to remove the honesty caveats from the documentation will be
  declined. The caveats describe the current code.

## Helping others

Answering a question in Discussions, reproducing a report on your hardware, or
attaching a bare-metal boot log is support work and is valued as much as a
patch. The project's open evidence gaps are listed in
[docs/SUPPORT-AND-FUNDING.md](docs/SUPPORT-AND-FUNDING.md#help-that-costs-nothing).
