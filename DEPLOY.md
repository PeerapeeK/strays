# Deploying StrayMatch to CT105 (Proxmox) behind Cloudflare Tunnel

Target: Debian/Ubuntu LXC `CT105` on Proxmox node `victus`, published at
`https://strays.peerapeek.cc`.

```
Visitor -> Cloudflare (HTTPS) -> Cloudflare Tunnel -> cloudflared in CT105
        -> nginx 127.0.0.1:8080 -> gunicorn /run/strays/gunicorn.sock -> Django
```

Nothing in the container listens on the LAN. The app lives in `/srv/strays`,
runs as system user `strays`, and reads secrets from `/etc/strays.env`
(outside the repo).

> Never run `seed_demo` in production: its demo passwords are public. Create
> the first administrator with `createsuperuser` (step 6).
> Never expose Proxmox port `8006` (or anything other than this site) through
> the tunnel.

## 1. Fix the LXC network check (run on the Proxmox node)

Run these from the Proxmox host shell. Replace `105` if your CT ID differs.

```bash
pct status 105
pct exec 105 -- ip -br addr
pct exec 105 -- ip route
pct exec 105 -- cat /etc/resolv.conf
```

- No IPv4 address: configure the container NIC in the Proxmox UI
  (CT105 -> Network) or edit `/etc/network/interfaces` inside the CT:
  ```bash
  pct exec 105 -- nano /etc/network/interfaces
  ```
  DHCP example:
  ```
  auto eth0
  iface eth0 inet dhcp
  ```
  Static example (adjust to your LAN):
  ```
  auto eth0
  iface eth0 inet static
      address 192.168.1.105/24
      gateway 192.168.1.1
  ```
- Missing default route: set the gateway in the Proxmox NIC config or in
  `/etc/network/interfaces`, then restart networking.
- DNS failures: set working resolvers inside the CT, e.g.
  ```bash
  pct exec 105 -- sh -c 'echo "nameserver 1.1.1.1" > /etc/resolv.conf'
  ```
  (On Debian 12+ you may need to set this in the network config instead so it
  survives reboots.)

Apply and verify outbound connectivity (the tunnel needs outbound TCP/UDP 443):

```bash
pct exec 105 -- systemctl restart networking
pct exec 105 -- ip route
pct exec 105 -- ping -c 2 1.1.1.1
pct exec 105 -- getent hosts deb.debian.org
```

## 2. Put the repo in place

```bash
sudo apt-get update
sudo apt-get install -y git
sudo git clone <your-repo-url> /srv/strays
```

If `/srv/strays` already exists from another copy, skip the clone.

## 3. Run provision.sh

```bash
sudo /srv/strays/deploy/provision.sh
```

Idempotent. It installs packages, creates the `strays` user and
`/srv/strays/.venv`, installs `strays.service` and the nginx site, removes the
default nginx site (so nothing listens on the LAN), and enables the services.
It does **not** create secrets and does **not** touch cloudflared.

## 4. Create `/etc/strays.env` (mode 600)

```bash
sudo install -m 600 -o strays -g strays /dev/null /etc/strays.env
sudo nano /etc/strays.env
```

Use `deploy/strays.env.example` as the template and replace every placeholder:

```ini
DEBUG=False
SECRET_KEY=<paste a long random value>
ALLOWED_HOSTS=strays.peerapeek.cc
CSRF_TRUSTED_ORIGINS=https://strays.peerapeek.cc
SECURE_HSTS_SECONDS=3600
```

Generate the secret without writing it into the repo:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

Check permissions:

```bash
sudo chmod 600 /etc/strays.env
sudo chown strays:strays /etc/strays.env
sudo ls -l /etc/strays.env
```

## 5. First deploy (pull, install, migrate, collectstatic, restart)

```bash
sudo /srv/strays/deploy/deploy.sh
```

For later releases, run the same command. If you need a manual check:

```bash
sudo -u strays env HOME=/srv/strays bash -c \
  'set -a; . /etc/strays.env; set +a; \
   /srv/strays/.venv/bin/python /srv/strays/manage.py check --deploy'
```

## 6. Create the administrator account

Do **not** run `seed_demo`.

```bash
sudo -u strays env HOME=/srv/strays bash -c \
  'set -a; . /etc/strays.env; set +a; \
   /srv/strays/.venv/bin/python /srv/strays/manage.py createsuperuser'
```

The superuser counts as the `Admin` role. Additional Staff/Adopter accounts are
managed from the app.

## 7. Install cloudflared and register the tunnel

In the Cloudflare dashboard: **Zero Trust -> Networks -> Tunnels -> Create a
tunnel**. Choose the `cloudflared` connector, copy the token shown, and keep the
dashboard open for step 8. Never commit the token.

On CT105:

```bash
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
  | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main" \
  | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt-get update
sudo apt-get install -y cloudflared
sudo cloudflared service install <TUNNEL_TOKEN>
sudo systemctl enable --now cloudflared
sudo systemctl status cloudflared --no-pager
```

## 8. Add the public hostname in Cloudflare

In the same tunnel: **Public Hostname -> Add a public hostname**.

- Subdomain: `strays`
- Domain: `peerapeek.cc`
- Path: (leave empty)
- Service type: `HTTP`
- URL: `localhost:8080`

Save. Cloudflare creates the DNS record automatically. Do not add a public
hostname for Proxmox `8006` or any other service.

## 9. Verification checklist

- [ ] `systemctl is-active strays nginx cloudflared` prints `active` three times.
- [ ] nginx listens only on loopback:
  ```bash
  sudo ss -ltnp | grep 8080     # 127.0.0.1:8080 only
  sudo ss -ltn | grep -E ':(80|443|8006)\b' || true   # no app ports on the LAN
  ```
- [ ] Gunicorn responds through the unix socket:
  ```bash
  curl -s -H 'Host: strays.peerapeek.cc' -H 'X-Forwarded-Proto: https' \
    --unix-socket /run/strays/gunicorn.sock http://localhost/healthz/
  ```
  Expected: `ok` (HTTP 200).
- [ ] nginx responds on loopback:
  ```bash
  curl -s -H 'Host: strays.peerapeek.cc' -H 'X-Forwarded-Proto: https' \
    http://127.0.0.1:8080/healthz/
  ```
  Expected: `ok`.
- [ ] Public site loads: `https://strays.peerapeek.cc/healthz/` returns `ok`.
- [ ] Private media is not directly reachable:
  ```bash
  curl -s -o /dev/null -w '%{http_code}\n' \
    https://strays.peerapeek.cc/media/profiles/example.jpg
  ```
  Expected: `404`. A logged-in owner/staff/admin can still view the file
  through `/files/<kind>/<id>/`.
- [ ] Dog photos still load from `/media/dogs/` (when a dog has a photo).
- [ ] Login works, and after five bad passwords the Thai lockout page appears
  for about fifteen minutes.
- [ ] `sudo journalctl -u strays -u nginx -u cloudflared -n 50 --no-pager`
  shows no errors.
- [ ] Backups: copy `db.sqlite3` and `media/` somewhere safe; `/etc/strays.env`
  has no copy in the repo.
