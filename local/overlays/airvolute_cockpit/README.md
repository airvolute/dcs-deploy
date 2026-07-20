# Airvolute Cockpit overlay

This overlay integrates Cockpit into a flashed DCS image without maintaining a
fork of Cockpit.

## Production package source

In production, this overlay should get Airvolute Cockpit packages from a
versioned artifact built by the `airvolute-cockpit-packages` repository.
Configure the artifact URL in `local/config_db.json`:

```json
"cockpit_packages": "https://airvolute.com/download/dcs_deploy/airvolute-cockpit-packages-1.2.3.tar.gz"
```

`dcs-deploy` downloads that archive with the other deployment resources and
passes it to this overlay as `cockpit_packages_archive=...`.

For local development, build the artifact in `airvolute-cockpit-packages` with
`make dist`, then pass it directly to `dcs-deploy`:

```sh
python3 dcs_deploy.py flash orin_nx 62 2.0 default nvme full \
  --rootfs=/path/to/rootfs_merged.tar.bz2 \
  --cockpit-packages=/path/to/airvolute-cockpit-packages-<version>.tar.gz \
  --regen
```

The archive must contain this structure, either at the top level or under one
top-level directory:

```text
packages/
  airvolute-package-manager/
  airvolute-services/
  airvolute-traffic-monitor/
  airvolute-doodle-radio/
branding/
password-policy/
```

The `packages/*` directories are prebuilt Cockpit package outputs. The
`branding` and `password-policy` directories are support payloads used by the
first-boot setup.

If no `cockpit_packages` artifact is configured, the overlay falls back to
`resources/packages`. This is only for development/migration; the production
source of truth should be the release artifact from `airvolute-cockpit-packages`.

## What it installs into the rootfs

- Prebuilt Airvolute Cockpit pages under `/usr/local/share/cockpit/`
- Airvolute branding assets under `/usr/local/share/airvolute/cockpit/branding`
- Airvolute password-policy script under
  `/usr/local/share/airvolute/cockpit/password-policy`
- A first-boot service:
  `/etc/systemd/system/airvolute_cockpit_first_boot.service`

## What happens on first boot

The first-boot service runs `/usr/local/bin/airvolute_cockpit_first_boot.sh`.
It installs official Ubuntu Cockpit packages with apt:

```text
cockpit
cockpit-networkmanager
cockpit-packagekit
cockpit-storaged
tcpdump
```

Then it applies branding, installs the password-policy script into Cockpit's
shell package, enables `cockpit.socket`, and writes this marker:

```text
/var/lib/airvolute/cockpit-setup.done
```

If apt/network is not ready, the service fails and retries.

## Why this design

Official Cockpit stays managed by Ubuntu packages and remains upgradable with
apt. Airvolute custom pages are static Cockpit packages on top of that base.
This avoids maintaining a downstream Cockpit fork.
