# Private Network Service Platform — Phase 2 Final Report

**Team:** Team 1 (Solo)  
**Domain:** `team1.test` (`app.team1.test`, `api.team1.test`)  
**Host Environment:** macOS (`Pihus-MacBook-Pro.local`) — `dnsmasq 2.93`, `nginx/1.31.6`, `Python 3.12.5`  
**Phase 1 Baseline:** [Architecture_Document.pdf](../01_Architecture/Architecture_Document.pdf)  
**Phase 2 Evidence Index:** [04_Evidence/Phase2/README.md](../04_Evidence/Phase2/README.md)

---

## Declaration

Consistent with Phase 1, all logical network roles run on a single MacBook using dedicated loopback aliases on `lo0` so real DNS, TCP, TLS, HTTP, and load-balancing traffic can be generated and inspected locally without cloud infrastructure. Phase 2 extends the Phase 1 loopback layout (`127.0.0.11`–`127.0.0.14`) by adding `127.0.0.15` (Backup DNS) and `127.0.0.16` (Standby Edge).

---

## 1. What Changed from Phase 1

Phase 1 built and observed the core pipeline (`Client → DNS → Edge/TLS/LB → Backends`). Phase 2 hardens the existing infrastructure without rebuilding from scratch.

### 1.1 Architecture & Configuration Delta

| Area | Phase 1 State | Phase 2 Addition / Change |
|---|---|---|
| **Loopback Roles** | `127.0.0.11` (DNS), `127.0.0.12` (Edge), `127.0.0.13:3001` (Backend A), `127.0.0.14:3002` (Backend B) | Added `127.0.0.15` (Backup `dnsmasq`) and `127.0.0.16` (Standby `nginx` edge) |
| **DNS Resolution** | Single `dnsmasq` at `127.0.0.11:53`; `/etc/resolver/team1.test` had one `nameserver 127.0.0.11` | Secondary `dnsmasq` (`05_Phase2_Config/dns-backup/dnsmasq-backup.conf`) at `127.0.0.15:53`; `/etc/resolver/team1.test` updated with both `127.0.0.11` and `127.0.0.15` |
| **TTL & Cache Control** | `local-ttl=30` configured in `dnsmasq.conf` | Verified 30s TTL via `dig` and `dscacheutil`, plus explicit macOS cache flush (`dscacheutil -flushcache` + `killall -HUP mDNSResponder`) |
| **Service Isolation** | Backends bound to `0.0.0.0:3001` and `0.0.0.0:3002` with no firewall filtering | Evaluated macOS `pfctl` anchor (`com.apple/cn_phase2_backend`) and verified clean rule rollback & nginx restoration |
| **HA & Failover** | `max_fails=1 fail_timeout=10s` and `proxy_next_upstream` configured in `team1.conf` | Tested backend recovery after `fail_timeout=10s` (`sleep 12`) and verified round-robin resumption (`A, B, A, B...`) |
| **Edge Migration** | Single nginx edge on `127.0.0.12` (recognized as a SPOF) | Drafted standby nginx (`127.0.0.16`) configuration and DNS cutover workflow (`05_Phase2_Config/edge-standby/`) |

### 1.2 Updated Request Flow & Single Point of Failure (SPOF) Analysis

```text
Client (curl / browser / dig)
  │
  ├──► DNS Lookup (scoped via /etc/resolver/team1.test)
  │      ├── Primary: 127.0.0.11:53 (dnsmasq)
  │      └── Backup:  127.0.0.15:53 (dnsmasq-backup, used if .11 stops)
  │            └─► Returns A record: 127.0.0.12 (or 127.0.0.16 during edge cutover)
  │
  └──► HTTPS Request (TLS 1.2/1.3 terminated at Edge)
         ├── Primary Edge: 127.0.0.12:443 (nginx, X-Edge: mac2-nginx)
         └── Standby Edge: 127.0.0.16:443 (nginx-standby, X-Edge: standby-nginx)
               │
               ├──► Backend A: 127.0.0.13:3001 (X-Backend: A)
               └──► Backend B: 127.0.0.14:3002 (X-Backend: B)
```

- **Remaining Single Point of Failure:** When running only the primary nginx instance on `127.0.0.12`, the **edge reverse proxy itself** is the single point of failure: even if both backends are healthy, if the `127.0.0.12` nginx process stops, client HTTPS connections fail.
- **How to eliminate it:** Deploy an active/standby or active/active pair of edge proxies (as modeled in Extension E with `127.0.0.16`) combined with either short-TTL DNS failover, anycast/VIP failover (e.g., VRRP/keepalived), or an upstream L4 load balancer.

---

## 2. Resilience Tests and Results

### 2.0 Phase 2 Baseline Verification
- **Evidence:** [P2_01](../04_Evidence/Phase2/00_Baseline/P2_01_baseline_nginx_resolver_loopback.jpg), [P2_02](../04_Evidence/Phase2/00_Baseline/P2_02_baseline_versions_and_files.jpg), [P2_03](../04_Evidence/Phase2/00_Baseline/P2_03_baseline_backends_dns_lb.jpg)
- **Observed Results:**
  - Confirmed software versions: `dnsmasq 2.93`, `nginx/1.31.6`, `Python 3.12.5`.
  - Loopback aliases `127.0.0.11`–`127.0.0.14` active on `lo0`.
  - Backends A (`3001`) and B (`3002`) returned `HTTP 200` directly.
  - `dig @127.0.0.11 app.team1.test` returned `127.0.0.12` (TTL `30`, query time `1 msec`).
  - Six consecutive HTTPS calls to `https://app.team1.test/api/status` returned `HTTP/2 200`, `x-edge: mac2-nginx`, and alternating `x-backend: B, A, B, A, B, A`.

### 2.1 Extension A — Backup DNS Resolver (Verified)
- **Evidence:** [P2_A1](../04_Evidence/Phase2/Extension_A_Backup_DNS/P2_A1_backup_dns_setup_and_launch.jpg), [P2_A2](../04_Evidence/Phase2/Extension_A_Backup_DNS/P2_A2_dual_dns_listeners_port53.jpg), [P2_A3](../04_Evidence/Phase2/Extension_A_Backup_DNS/P2_A3_backup_dns_failover_verified.jpg)
- **Actions & Commands:**
  - Backed up `dnsmasq.conf`, `team1.conf`, and `/etc/resolver/team1.test`.
  - Brought up `127.0.0.15` on `lo0` and created `dnsmasq-backup.conf` (`listen-address=127.0.0.15`, `port=53`, `local-ttl=30`).
  - Verified `dnsmasq --test` (`syntax check OK`) and launched backup `dnsmasq` (`--no-daemon`).
  - Confirmed via `sudo lsof -nP -iUDP:53 -iTCP:53` that both PID `2240` (`127.0.0.11:53`) and PID `3046` (`127.0.0.15:53`) were listening on UDP and TCP.
  - Updated `/etc/resolver/team1.test` with both `127.0.0.11` and `127.0.0.15` and verified via `scutil --dns` (`resolver #9`, `nameserver[0]: 127.0.0.11`, `nameserver[1]: 127.0.0.15`).
  - Stopped primary DNS (`sudo brew services stop dnsmasq`) and queried again.
- **Result:** Even with primary `dnsmasq` stopped, `dig @127.0.0.15 app.team1.test +short` and macOS system lookup (`dscacheutil -q host -a name app.team1.test`) continued returning `127.0.0.12`.
- **DNS Failure vs. Application Failure:** A DNS service failure prevents hostname-to-IP resolution before any TCP handshake begins, whereas an application/backend failure allows DNS resolution (and even edge TLS) to succeed while HTTP requests return `502 Bad Gateway` or connection errors.

### 2.2 Extension B — DNS TTL and Controlled Record Change (Partial Capture)
- **Evidence:** [P2_B1](../04_Evidence/Phase2/Extension_B_DNS_TTL/P2_B1_ttl_30s_and_cache_flush.jpg), [P2_B2](../04_Evidence/Phase2/Extension_B_DNS_TTL/P2_B2_dnsmasq_restart_and_verify.jpg)
- **Observed Results:**
  - `grep -E 'host-record|local-ttl' /opt/homebrew/etc/dnsmasq.conf` confirmed `local-ttl=30` and `host-record=app.team1.test,127.0.0.12`.
  - `dig @127.0.0.11 app.team1.test +noall +answer` returned `app.team1.test. 30 IN A 127.0.0.12`.
  - macOS cache inspection (`dscacheutil -q host -a name app.team1.test`) and manual cache flush (`sudo dscacheutil -flushcache && sudo killall -HUP mDNSResponder`) were executed, followed by `sudo brew services restart dnsmasq` and verification.
- **Note / Gap:** The uploaded captures demonstrate the `30s` TTL record, cache inspection, cache flush, and service restart; an additional before/after screenshot showing a stale cached IP expiring automatically after 30s when switching `host-record` to a different IP can be captured during final verification if needed.

### 2.3 Extension C — Service Isolation / Backend Firewall Rules (Partial Capture + Rollback Verified)
- **Evidence:** [P2_C1](../04_Evidence/Phase2/Extension_C_Service_Isolation/P2_C1_pf_state_and_direct_vs_edge.jpg), [P2_C2](../04_Evidence/Phase2/Extension_C_Service_Isolation/P2_C2_pf_anchor_rollback_nginx_reload.jpg)
- **Observed Results:**
  - `P2_C1` shows `pfctl` state table/counters (`current entries 0`), successful edge access (`curl https://app.team1.test/api/status` → `HTTP/2 200`, `x-edge: mac2-nginx`), and direct curls to `127.0.0.13:3001` and `127.0.0.14:3002`. In that capture, the direct backend curls still returned `HTTP/1.0 200 OK` because macOS's default `/etc/pf.conf` specifies `set skip on lo0`, causing loopback packets to bypass PF unless `lo0` is removed from `skip` or tested across separate LAN hosts.
  - `P2_C2` verifies clean rollback: `sudo pfctl -a com.apple/cn_phase2_backend -F rules` (`rules cleared`), restoration of `nginx-before-firewall.conf`, and `sudo nginx -t && sudo nginx -s reload` (`syntax is ok`, `test is successful`).
- **Template Added:** [backend_isolation_anchor.conf](../05_Phase2_Config/pf/backend_isolation_anchor.conf) documents the PF anchor rules and the `lo0` caveat.

### 2.4 Extension D — High-Availability Failover Behavior (Verified Recovery)
- **Evidence:** [P2_D1](../04_Evidence/Phase2/Extension_D_HA_Failover/P2_D1_lb_verify_and_failover_prep.jpg), [P2_D2](../04_Evidence/Phase2/Extension_D_HA_Failover/P2_D2_backend_recovery_round_robin.jpg) (paired with Phase 1 single-backend-down evidence [H3_one_backend_down.png](../04_Evidence/H_Failures/H3_one_backend_down.png))
- **Observed Results:**
  - `P2_D1` confirms both backends listening on `3001` and `3002` and 6 HTTPS requests alternating `x-backend: A, B, A, B, A, B`.
  - `P2_D2` shows waiting `sleep 12` (exceeding nginx's `fail_timeout=10s` in `upstream team1_backends`), after which 8 consecutive HTTPS requests returned `x-backend: A, B, A, B, A, B, A, B`, proving nginx automatically re-included Backend A once its health window reset.

### 2.5 Extension E — Controlled Edge Migration / DNS-Based Cutover (Work in Progress)
- **Evidence:** [P2_E1](../04_Evidence/Phase2/Extension_E_Edge_Migration/P2_E1_standby_nginx_and_cutover_wip.jpg)
- **Observed Results & Next Steps:**
  - `P2_E1` captures creating `nginx-standby.conf`, testing with `nginx -t -c ...` (which failed because `team1_standby.conf` had not yet been created), verifying `127.0.0.16:443` was not yet listening (`curl: (7) Couldn't connect to server`), backing up `dnsmasq.conf` to `dnsmasq-before-edge-migration.conf`, and starting the `sed` cutover command (paused at an unclosed quote `dquote>`).
  - Complete, syntax-clean standby configs have now been added to [05_Phase2_Config/edge-standby/](../05_Phase2_Config/edge-standby/) (`nginx-standby.conf` and `team1_standby.conf`) so the cutover can be executed cleanly during the live demo.

---

## 3. Troubleshooting Findings & Diagnostic Methodology

### 3.1 Systematic Layer-by-Layer Diagnosis (Extension F Methodology)

When a fault is injected (during Extension F or live testing), diagnosis proceeds strictly bottom-up / request-path ordered:

1. **Layer 1 — Name Resolution (DNS):**
   - Check `/etc/resolver/team1.test` and `scutil --dns | grep -B1 -A7 team1.test`.
   - Query `dig @127.0.0.11 app.team1.test` and `dig @127.0.0.15 app.team1.test` directly to isolate server failure vs. client resolver config vs. stale cache (`dscacheutil -flushcache`).
2. **Layer 2 — Network & Transport (IP / Ports / TCP):**
   - Verify loopback aliases (`ifconfig lo0 | grep 'inet 127'`) or LAN reachability (`ping`).
   - Check listening sockets (`sudo lsof -nP -iUDP:53 -iTCP:53`, `lsof -nP -iTCP:443,3001,3002 -sTCP:LISTEN`).
   - Verify whether PF firewall rules (`sudo pfctl -a com.apple/cn_phase2_backend -s rules`) are dropping packets.
3. **Layer 3 — Security (TLS Handshake & Trust):**
   - Test with `curl -v https://app.team1.test/api/status` (no `-k` flag) to confirm certificate SANs, expiry, and System Keychain trust for `team1-rootCA.pem`.
4. **Layer 4 — Edge & Application (Nginx / Backends):**
   - Run `sudo nginx -t` to validate syntax and check `/opt/homebrew/var/log/nginx/team1_access.log` and `error.log`.
   - Test backends directly (`curl -i http://127.0.0.13:3001/api/status`, `http://127.0.0.14:3002/api/status`) to separate upstream crashes (`502 Bad Gateway`) from reverse-proxy misconfiguration.

### 3.2 Real Issues Observed During Phase 2 Execution

| Issue Observed | Screenshot | Root Cause | Resolution / Lesson |
|---|---|---|---|
| `OSError: [Errno 48] Address already in use` | [P2_D2](../04_Evidence/Phase2/Extension_D_HA_Failover/P2_D2_backend_recovery_round_robin.jpg) | Port `3001` was already bound by an active `backend.py A 3001` process. | Check `lsof -nP -iTCP:3001 -sTCP:LISTEN` before starting a backend instance. |
| `open() ".../team1_standby.conf" failed (2: No such file or directory)` | [P2_E1](../04_Evidence/Phase2/Extension_E_Edge_Migration/P2_E1_standby_nginx_and_cutover_wip.jpg) | `nginx-standby.conf` included `team1_standby.conf` before that file was created. | Create included server-block files before running `nginx -t -c`. |
| `cp: .../dnsmasq-before-ttl-change.conf: No such file or directory` | [P2_B2](../04_Evidence/Phase2/Extension_B_DNS_TTL/P2_B2_dnsmasq_restart_and_verify.jpg) | Rollback path differed from `Phase2_Backups/dnsmasq.conf.backup`. | Standardize backup paths inside one backup folder (`Phase2_Backups/`). |
| Direct backend curls succeeded during PF check | [P2_C1](../04_Evidence/Phase2/Extension_C_Service_Isolation/P2_C1_pf_state_and_direct_vs_edge.jpg) | macOS default `/etc/pf.conf` has `set skip on lo0`, bypassing PF on loopback traffic. | On single-host loopback tests, `lo0` must not be skipped in PF (or isolate across physical LAN hosts). |
| Unfinished `sed` command (`dquote>`) | [P2_E1](../04_Evidence/Phase2/Extension_E_Edge_Migration/P2_E1_standby_nginx_and_cutover_wip.jpg) | Missing closing double-quote on `"$BREW_PREFIX/etc/dnsmasq.conf"`. | Verify command quoting and run `dnsmasq --test` before restarting `dnsmasq`. |

---

## 4. Learning Summary (One Paragraph per Extension)

**Extension A — Backup DNS Resolver:** Adding a secondary `dnsmasq` instance on `127.0.0.15` and listing both resolvers in `/etc/resolver/team1.test` demonstrated how client-side DNS redundancy eliminates DNS as a single point of failure. When the primary DNS server on `127.0.0.11` was intentionally stopped, macOS transparently failed over to `127.0.0.15` and continued resolving `app.team1.test` to `127.0.0.12`. This reinforced the separation between name resolution and application transport: DNS outage breaks discovery even when the edge and backends are completely healthy, whereas backup resolvers preserve service reachability without modifying the edge or backend tiers.

**Extension B — DNS TTL and Controlled Record Change:** Configuring `local-ttl=30` and inspecting responses with `dig` and `dscacheutil` highlighted how DNS caching trades propagation speed for reduced query load. Clients and OS stub resolvers reuse cached A records until the TTL expires, meaning a record change does not take effect instantaneously for existing clients unless caches are explicitly flushed (e.g., via `dscacheutil -flushcache` and `killall -HUP mDNSResponder`). In production systems, lowering TTL well ahead of a planned migration prepares clients for a faster, smoother cutover.

**Extension C — Service Isolation (Backend Firewall Rules):** Attempting to lock down ports `3001` and `3002` so only the nginx edge (`127.0.0.12`) can reach the backends clarified the principle of defense in depth: reverse proxies enforce TLS, routing, and headers only if clients cannot bypass the edge and connect straight to backend sockets. Investigating the macOS `pfctl` state table and anchor rollback also revealed an important host-networking detail—macOS skips PF filtering on `lo0` by default (`set skip on lo0`), which explains why single-host loopback isolation behaves differently from multi-host `en0` LAN firewalling.

**Extension D — High-Availability Failover Behavior:** Testing nginx upstream resilience (`max_fails=1`, `fail_timeout=10s`, `proxy_next_upstream`) showed how an edge load balancer masks individual backend failures from clients and automatically restores capacity once a failed node recovers. Waiting past the `10s` `fail_timeout` window (`sleep 12`) allowed nginx to re-probe Backend A and seamlessly resume round-robin alternation (`A, B, A, B`). At the same time, this confirmed that the edge reverse proxy itself remains a single point of failure unless paired with a standby or multi-edge architecture.

**Extension E — Controlled Edge Migration (DNS-Based Cutover):** Preparing a standby nginx instance on `127.0.0.16` and attempting to migrate `app.team1.test` via DNS demonstrated how edge-tier high availability and blue-green/standby cutovers work without replacing backend servers. Encountering the missing `team1_standby.conf` include during `nginx -t` underscored why pre-flight configuration validation (`nginx -t`) and health verification (`curl --resolve`) must pass *before* updating DNS records to shift live client traffic.

**Extension F — Systematic Troubleshooting:** Debugging real configuration errors encountered during Phase 2 (`Address already in use`, missing include files, backup path mismatches, and PF loopback behavior) alongside the Phase 1 failure scenarios reinforced the value of a strict layer-by-layer diagnostic workflow. Checking DNS resolution first, then socket listeners and firewall rules, then TLS validation, and finally nginx upstream logs prevents guesswork and isolates root causes quickly under evaluation pressure.

---

## 5. Final 11-Step Demonstration Mapping

| Step | Demo Requirement | Where to Show in This Repo |
|---|---|---|
| 1 | Topology & IP/service inventory | [Architecture_Document.pdf](../01_Architecture/Architecture_Document.pdf), [phase2_network_setup.md](../05_Phase2_Config/phase2_network_setup.md) |
| 2 | Private LAN / loopback reachability | [04_Evidence/A_LAN/](../04_Evidence/A_LAN/), [P2_01](../04_Evidence/Phase2/00_Baseline/P2_01_baseline_nginx_resolver_loopback.jpg) |
| 3 | Private DNS resolution (`dig`) | [04_Evidence/B_DNS/](../04_Evidence/B_DNS/), [P2_03](../04_Evidence/Phase2/00_Baseline/P2_03_baseline_backends_dns_lb.jpg) |
| 4 | HTTPS via domain name (trusted CA) | [04_Evidence/E_TLS/](../04_Evidence/E_TLS/) |
| 5 | Load balancing (`X-Backend: A/B`) | [04_Evidence/D_LoadBalancer/](../04_Evidence/D_LoadBalancer/), [P2_D1](../04_Evidence/Phase2/Extension_D_HA_Failover/P2_D1_lb_verify_and_failover_prep.jpg) |
| 6 | Wireshark DNS / TCP / TLS captures | [04_Evidence/G_Captures/](../04_Evidence/G_Captures/) |
| 7 | HTTP `Cache-Control` & `304` | [04_Evidence/F_Caching/](../04_Evidence/F_Caching/) |
| 8 | Backend failover & recovery | [H3_one_backend_down.png](../04_Evidence/H_Failures/H3_one_backend_down.png), [P2_D2](../04_Evidence/Phase2/Extension_D_HA_Failover/P2_D2_backend_recovery_round_robin.jpg) |
| 9 | Phase 2 backup DNS, TTL, cutover | [04_Evidence/Phase2/](../04_Evidence/Phase2/README.md) |
| 10 | Live fault diagnosis | Section 3.1 methodology above |
| 11 | Individual viva | Section 4 learning summaries & protocol explanations |
