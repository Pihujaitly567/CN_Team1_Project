# Phase 2 Network & Resilience Setup Guide

Phase 2 extends the Phase 1 loopback topology (`127.0.0.11`–`127.0.0.14`) without rebuilding from scratch.

## 1. Extended Loopback Role Map

| Logical Role | Loopback IP | Service | Port / Protocol | Phase |
|---|---|---|---|---|
| Mac 1 — Primary DNS | `127.0.0.11` | `dnsmasq` (Homebrew) | `53 / UDP + TCP` | Phase 1 + 2 |
| Mac 2 — Primary Edge + LB | `127.0.0.12` | `nginx` | `80, 443 / TCP` | Phase 1 + 2 |
| Mac 3 — Backend A | `127.0.0.13` | `backend.py A` | `3001 / TCP` | Phase 1 + 2 |
| Mac 4 — Backend B | `127.0.0.14` | `backend.py B` | `3002 / TCP` | Phase 1 + 2 |
| Backup DNS Resolver | `127.0.0.15` | `dnsmasq` (`dnsmasq-backup.conf`) | `53 / UDP + TCP` | Phase 2 (Ext A) |
| Standby Edge + LB | `127.0.0.16` | `nginx` (`nginx-standby.conf`) | `80, 443 / TCP` | Phase 2 (Ext E) |

Bring up all loopback aliases on macOS:

```zsh
for i in 11 12 13 14 15 16; do sudo ifconfig lo0 alias 127.0.0.$i up; done
ifconfig lo0 | grep 'inet 127'
```

## 2. Extension A — Backup DNS Resolver

1. Start the backup `dnsmasq` instance bound to `127.0.0.15`:
   ```zsh
   dnsmasq --test -C 05_Phase2_Config/dns-backup/dnsmasq-backup.conf
   sudo dnsmasq --no-daemon --conf-file="$(pwd)/05_Phase2_Config/dns-backup/dnsmasq-backup.conf"
   ```
2. Update `/etc/resolver/team1.test` to list both primary and backup resolvers:
   ```zsh
   sudo cp /etc/resolver/team1.test /etc/resolver/team1.test.phase2-backup
   sudo cp 05_Phase2_Config/dns-backup/resolver_team1.test.phase2 /etc/resolver/team1.test
   sudo dscacheutil -flushcache && sudo killall -HUP mDNSResponder
   scutil --dns | grep -B1 -A7 team1.test
   ```
3. Stop primary `dnsmasq` and verify resolution continues via `127.0.0.15`:
   ```zsh
   sudo brew services stop dnsmasq
   dig @127.0.0.15 app.team1.test +short
   dscacheutil -q host -a name app.team1.test
   ```

## 3. Extension B — DNS TTL & Cache Flush

- `local-ttl=30` in `dnsmasq.conf` sets a 30-second DNS TTL.
- Flush macOS resolver cache after updating records:
  ```zsh
  sudo dscacheutil -flushcache
  sudo killall -HUP mDNSResponder
  ```

## 4. Extension C — Service Isolation (PF Anchor) & Rollback

```zsh
# Verify / clear project PF anchor rules during rollback
sudo pfctl -a com.apple/cn_phase2_backend -s rules
sudo pfctl -a com.apple/cn_phase2_backend -F rules
```

> Note: On single-Mac loopback deployments, macOS's default `/etc/pf.conf` has `set skip on lo0`, which bypasses PF on loopback traffic unless `lo0` is explicitly included or roles run on separate LAN hosts.

## 5. Extension D — High-Availability Failover

Nginx uses `max_fails=1 fail_timeout=10s` and `proxy_next_upstream error timeout http_502 http_503;`.
- Stopping Backend A causes nginx to route exclusively to Backend B.
- Restarting Backend A and waiting >10s (`sleep 12`) allows nginx to mark Backend A healthy again and resume round-robin balancing.

## 6. Extension E — Controlled Edge Migration (Standby Nginx)

```zsh
nginx -t -c "$(pwd)/05_Phase2_Config/edge-standby/nginx-standby.conf"
sudo nginx -c "$(pwd)/05_Phase2_Config/edge-standby/nginx-standby.conf"
curl --resolve app.team1.test:443:127.0.0.16 -sS -D - https://app.team1.test/api/status -o /dev/null
```
Then update `host-record=app.team1.test,127.0.0.16` in `dnsmasq.conf` and restart `dnsmasq` to observe DNS-based cutover and TTL caching effects.
