# Self-healing

`grintion-selfheal` repairs the broken states that most often leave a booted
system unusable. It runs once after `boot-health`, then sleeps; `boot-health`
still owns boot-attempt counting and Limine auto-revert.

```sh
sudo grintion-selfheal plan          # what would be repaired
sudo grintion-selfheal --dry-run     # same, without changes
sudo grintion-selfheal run --json    # repair and report
grintion-selfheal status             # last recorded run
```

Repairs are intentionally small and reversible:

- restore `1777` on `/tmp` and `/var/tmp`;
- remount the root read-write when it is read-only;
- remove broken `/var/service` symlinks;
- remove a `garb` lock whose holder is dead;
- restore fallback nameservers when `/etc/resolv.conf` is empty;
- bring the loopback interface up;
- load AppArmor profiles when the kernel has none;
- start zram swap when the device exists but is not active;
- restart enabled services that are down.

Every action is appended to `/var/log/grintion-selfheal.log`. A failed critical
repair (for example a read-only root that cannot be remounted) exits nonzero so
`sv status selfheal` shows the failure.

`grintion-doctor` performs the same checks without changing state and adds
firmware, kernel-feature, snapshot, disk, boot-health and time/DNS checks.
