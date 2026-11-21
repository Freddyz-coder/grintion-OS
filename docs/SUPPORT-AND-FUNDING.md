# Support and funding

This page documents the support and donation infrastructure that lives in this
repository, and the one-time setup that has to happen outside it.

Files:

| Path | Purpose |
| --- | --- |
| `site/index.html` | The public support page: funding, community links, policy. No scripts, fonts or analytics. |
| `.github/workflows/pages.yml` | Publishes `site/` to GitHub Pages on every change. |
| `.github/FUNDING.yml` | The repository's "Sponsor" button. |
| `SUPPORT.md` | Where to ask questions and how to report a problem. |
| `CODE_OF_CONDUCT.md` | Behaviour rules for project spaces. |
| `docs/FUNDING-LEDGER.md` | Public record of income and spend. |

None of this changes the image. No package, service or command is added to
Grintion-OS by publishing a support page.

---

## Setup checklist

These steps need the GitHub account **Freddyz-coder** and cannot be done from
inside the repository.

### 1. Enable GitHub Sponsors (the only payment channel wired up)

1. Open <https://github.com/sponsors> and choose **Join GitHub Sponsors**.
2. Complete the sponsor profile: a short description of the project, the
   funding goal, and what the money is used for. Reuse the "Where the money
   goes" section of `site/index.html`; it matches the release process.
3. Connect a bank account through Stripe Connect and complete the tax
   information. GitHub requires this before it can pay out.
4. Publish the profile. Until this is done,
   `https://github.com/sponsors/Freddyz-coder` returns a page without a sponsor
   form.
5. Optional: create tiers. Keep them honest. A tier must not promise a feature,
   a deadline or priority support; the funding policy on the site says a
   donation buys none of those.

One-time donations are available on the same page. GitHub covers payment
processing for individual sponsors, which is why it is the recommended channel.

### 2. Enable Discussions

Repository **Settings -> General -> Features -> Discussions**. The site and
`SUPPORT.md` both link to `/discussions`; the link 404s until this is on.
Suggested categories: *Q&A*, *Hardware reports*, *Show your setup*, *Packaging*.

### 3. Publish the site with GitHub Pages

1. Repository **Settings -> Pages -> Build and deployment -> Source:
   GitHub Actions**.
2. Push a change under `site/` to `main`, or run the **Support site** workflow
   manually.
3. The URL is `https://freddyz-coder.github.io/grintion-OS/` unless a custom
   domain is configured.

The workflow uploads only `site/`, so the rest of the repository is not served.
There is no Jekyll processing and no build step: the HTML is the artifact.

Verify after the first deploy:

```sh
curl -sI https://freddyz-coder.github.io/grintion-OS/ | head -n 1   # 200
```

### 4. Point the Sponsor button at the site (optional)

Once the site is live, uncomment the `custom:` line in `.github/FUNDING.yml`:

```yaml
custom: ["https://freddyz-coder.github.io/grintion-OS/"]
```

GitHub shows it next to the Sponsors link. Leave it commented until the URL
actually resolves; a funding link that 404s is worse than no link.

### 5. Add a second channel (optional)

The site has commented-out cards for Ko-fi (one-time) and Liberapay
(recurring, no platform cut). To enable one:

1. Create the account and copy the public handle.
2. Uncomment the matching card in `site/index.html` and replace `YOUR-HANDLE`.
3. Add the same handle to `.github/FUNDING.yml`.
4. Push. The Pages workflow redeploys automatically.

Do not add a channel that requires a company entity, a minimum volume, or a
paid plan. The project has none of those.

### 6. Custom domain (optional)

1. Add a file `site/CNAME` containing the bare domain, for example
   `grintion.example`.
2. At the DNS provider, create `CNAME grintion.example -> freddyz-coder.github.io`.
   Use `A`/`AAAA` records only for an apex domain.
3. In **Settings -> Pages**, set the custom domain and enable **Enforce HTTPS**.

`site/CNAME` is picked up because the workflow uploads the whole `site/`
directory.

---

## Keeping it honest

The repository's own rules apply to the funding page: do not claim what the
project cannot prove. In practice:

- Do not describe donations as tax-deductible. They are not.
- Do not claim the project is a nonprofit or a foundation.
- Do not promise that a sponsorship pays for a specific feature or a deadline.
- Do not publish a sponsor name without permission.
- Update [FUNDING-LEDGER.md](FUNDING-LEDGER.md) when a payout clears or an
  expense is paid. The page links to the ledger, so an empty ledger with real
  income is a broken promise.

## Help that costs nothing

These are the project's actual open gaps, and they are listed on the site
because they are worth more than a small donation:

| Gap | What closes it |
| --- | --- |
| No published bare-metal evidence | Boot the ISO on real hardware and attach the log to a Discussions post |
| Cross-host reproducibility unproven | Build the ISO on a second host and report `BUILD-INFO` and the artifact hash |
| Desktops verified only in QEMU | Test XFCE, i3, Plasma, LXQt or Sway on your GPU and report the result |
| Handbook only in English and Spanish | Translate `docs/HANDBOOK.md` |
| No hosted package repository | Not a volunteer task; it needs the funding above |

See [../SUPPORT.md](../SUPPORT.md) for where to post each of these.

## Maintenance

- After a release, check that the site's version string still matches `VERSION`.
- Once a month, add the income and expense rows to the ledger, or state that
  nothing changed.
- Review the "Where the money goes" cards when a gap closes; remove the card
  instead of leaving a stale goal on the page.
