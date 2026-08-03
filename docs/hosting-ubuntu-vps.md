# Supported 24/7 hosting target

ComradBot's supported unattended target is one Ubuntu Server 24.04 LTS VPS running the published
container with the Docker Engine and Docker Compose plugin. Use one bot replica, at least 1 vCPU,
2 GiB RAM, and enough disk for the `comradbot-data` volume. This target deliberately retains SQLite;
multiple replicas are unsupported.

## Host preparation

1. Provision an Ubuntu Server 24.04 LTS VPS and secure SSH access using your provider's guidance.
2. Install Docker Engine and the Docker Compose plugin from Docker's official Ubuntu instructions.
3. Create a dedicated deployment directory owned by the operator account:

   ```bash
   mkdir -p ~/comradbot
   cd ~/comradbot
   ```

4. Download `compose.production.yaml` and `.env.example` from the matching GitHub release, verify the
   release checksum, and rename `.env.example` to `.env`.
5. Restrict the environment file and configure at least `DISCORD_TOKEN`:

   ```bash
   chmod 600 .env
   ```

The bot does not expose an inbound TCP port. Do not publish container ports or grant the container
privileged access.

## Persistent storage

The Compose file mounts the named volume `comradbot-data` at `/app/data`. It contains SQLite,
custom sounds, temporary working directories, and the local health heartbeat. Confirm it exists
after the first start:

```bash
docker volume inspect comradbot-data
```

Never use `docker compose down --volumes` during routine maintenance. The container is replaceable;
the named volume is not. This guide does not claim automated backup support—the corresponding
persistence milestone remains deferred.

## Start and update

```bash
docker compose -f compose.production.yaml pull
docker compose -f compose.production.yaml up -d
docker compose -f compose.production.yaml ps
```

The service uses `restart: unless-stopped`, so Docker restarts it after a process failure or host
reboot unless an operator explicitly stopped it. To install a pinned newer release, replace the
Compose file and `.env.example` reference as needed, preserve `.env` and the named volume, then run
the same pull and up commands.

## External monitoring

Create a simple check in Healthchecks.io or a compatible dead-man's-switch service. Use a period
slightly longer than `EXTERNAL_MONITOR_INTERVAL_SECONDS` and an appropriate grace period. Add its
unique HTTPS ping URL to `.env`:

```env
EXTERNAL_MONITOR_PING_URL=https://hc-ping.com/replace-with-your-check-id
EXTERNAL_MONITOR_INTERVAL_SECONDS=60
EXTERNAL_MONITOR_TIMEOUT_SECONDS=5
```

Treat the URL as a secret because possession of it permits false check-ins. ComradBot sends only an
HTTP GET and no Discord, guild, user, prompt, or runtime content. Delivery failures are logged
without the URL and never terminate the bot. Recreate the service after environment changes:

```bash
docker compose -f compose.production.yaml up -d --force-recreate
```

Verify that the check receives pings, then test alerts by stopping the service long enough to exceed
the configured period and grace time. Start it again after the alert arrives.

## Routine checks

```bash
docker compose -f compose.production.yaml ps
docker compose -f compose.production.yaml logs --tail=100 comradbot
```

Docker's local health check and the external dead-man's switch serve different purposes. The local
check validates the runtime heartbeat, SQLite, FFmpeg, and FFprobe. The external check detects a
stopped container, failed host, or lost network path from outside the VPS.
