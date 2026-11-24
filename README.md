# Private Network Service Platform — CN Team 1 Project

A two-phase Computer Networks project implementing a complete local private service platform (`*.team1.test`) on macOS: **Private DNS (`dnsmasq`) → HTTPS Reverse Proxy & Load Balancer (`nginx`) → Dual REST Backends (`Python`)**, with full packet analysis (`Wireshark`) and Phase 2 resilience extensions.

> **Deployment Mode:** Solo implementation on macOS (`Pihus-MacBook-Pro.local`) modeling all logical machines on `lo0` loopback aliases (`127.0.0.11`–`127.0.0.16`). Real DNS, TCP, TLS, and HTTP packets are generated and captured on `lo0`.

---

## Architecture & Role Inventory (Phase 1 + Phase 2)

| Role | Cloud Equivalent | Loopback IP | Service | Port / Protocol | Phase |
|---|---|---|---|---|---|
| **Mac 1 — Primary DNS** | AWS Route 53 | `127.0.0.11` | `dnsmasq` | `53 / UDP + TCP` | Phase 1 + 2 |
| **Mac 2 — Primary Edge + LB** | AWS ALB / CDN Edge | `127.0.0.12` | `nginx` (TLS + LB) | `80, 443 / TCP` | Phase 1 + 2 |
| **Mac 3 — Backend A** | EC2 Instance A | `127.0.0.13` | `backend.py A` | `3001 / TCP` | Phase 1 + 2 |
| **Mac 4 — Backend B** | EC2 Instance B | `127.0.0.14` | `backend.py B` | `3002 / TCP` | Phase 1 + 2 |
| **Backup DNS Resolver** | Secondary Route 53 / NS | `127.0.0.15` | `dnsmasq` (`dnsmasq-backup.conf`) | `53 / UDP + TCP` | Phase 2 (Ext A) |
| **Standby Edge + LB** | Standby ALB / Edge Node | `127.0.0.16` | `nginx` (`nginx-standby.conf`) | `80, 443 / TCP` | Phase 2 (Ext E) |

```text
Client (curl / browser / dig)
  ├──► DNS (127.0.0.11 primary, 127.0.0.15 backup) ──► app.team1.test = 127.0.0.12 (TTL 30s)
  └──► HTTPS / HTTP2 (127.0.0.12:443 nginx TLS termination + round-robin LB)
         ├──► Backend A (127.0.0.13:3001)  [X-Backend: A]
         └──► Backend B (127.0.0.14:3002)  [X-Backend: B]
```

---

## Repository Structure

```text
CN_Team1_Project/
├── README.md                                  # Project overview, runbook & navigation
├── 01_Architecture/
│   ├── A3_topology.png                        # Network topology diagram
│   └── Architecture_Document.pdf              # Phase 1 Architecture Document
├── 02_Config/                                 # Phase 1 configuration bundle
│   ├── backend_launch.md
│   ├── dnsmasq.conf
│   ├── network_setup.md
│   ├── nginx_team1.conf
│   ├── resolver_team1.test.txt
│   └── tls_certificate_setup.md
├── 03_Backend/
│   └── backend.py                             # ThreadingHTTPServer REST backend (/, /api/status, /api/info)
├── 04_Evidence/
│   ├── A_LAN/ ... H_Failures/                 # Phase 1 evidence screenshots & .pcapng captures
│   └── Phase2/                                # Phase 2 screenshots & verification index
│       ├── README.md                          # Complete Phase 2 evidence index
│       ├── 00_Baseline/                       # Baseline versions, aliases, DNS & LB checks
│       ├── Extension_A_Backup_DNS/            # Dual DNS on .11 & .15 + primary stop failover
│       ├── Extension_B_DNS_TTL/               # local-ttl=30 check, cache flush & restart
│       ├── Extension_C_Service_Isolation/     # PF state check, anchor rollback & nginx reload
│       ├── Extension_D_HA_Failover/           # LB check & recovery after fail_timeout=10s
│       └── Extension_E_Edge_Migration/        # Standby nginx setup & cutover troubleshooting
├── 05_Phase2_Config/                          # Phase 2 configuration additions
│   ├── phase2_network_setup.md                # Phase 2 setup & test runbook
│   ├── dns-backup/
│   │   ├── dnsmasq-backup.conf
│   │   └── resolver_team1.test.phase2
│   ├── pf/
│   │   └── backend_isolation_anchor.conf
│   └── edge-standby/
│       ├── nginx-standby.conf
│       └── team1_standby.conf
└── 06_Report/
    └── Phase2_Final_Report.md                 # Full Phase 2 report (delta, tests, troubleshooting, learnings)
```

---

## Phase 1 Summary (Build & Observe)

- **Private LAN & Loopback Topology:** [02_Config/network_setup.md](02_Config/network_setup.md), [04_Evidence/A_LAN/](04_Evidence/A_LAN/)
- **Private DNS (`*.team1.test`):** [02_Config/dnsmasq.conf](02_Config/dnsmasq.conf), [04_Evidence/B_DNS/](04_Evidence/B_DNS/)
- **Dual REST Backends (`A` & `B`):** [03_Backend/backend.py](03_Backend/backend.py), [04_Evidence/C_Backends/](04_Evidence/C_Backends/)
- **Reverse Proxy & Round-Robin LB:** [02_Config/nginx_team1.conf](02_Config/nginx_team1.conf), [04_Evidence/D_LoadBalancer/](04_Evidence/D_LoadBalancer/)
- **HTTPS / TLS Termination & Local CA Trust:** [02_Config/tls_certificate_setup.md](02_Config/tls_certificate_setup.md), [04_Evidence/E_TLS/](04_Evidence/E_TLS/)
- **HTTP Caching (`Cache-Control: public, max-age=60`, `ETag`, `304 Not Modified`):** [04_Evidence/F_Caching/](04_Evidence/F_Caching/)
- **Wireshark Captures (DNS, TCP, TLS 1.2/1.3, Plaintext Backend Hop):** [04_Evidence/G_Captures/](04_Evidence/G_Captures/)
- **Controlled Failures (5 Scenarios):** [04_Evidence/H_Failures/](04_Evidence/H_Failures/)

---

## Phase 2 Summary (Harden, Recover & Troubleshoot)

Detailed results, troubleshooting notes, and extension-by-extension learnings are documented in **[06_Report/Phase2_Final_Report.md](06_Report/Phase2_Final_Report.md)** and indexed in **[04_Evidence/Phase2/README.md](04_Evidence/Phase2/README.md)**.

| Extension | Description | Config / Docs | Evidence Folder |
|---|---|---|---|
| **Baseline** | Verify Phase 1 stack, versions (`dnsmasq 2.93`, `nginx/1.31.6`, `Python 3.12.5`), loopback aliases | [phase2_network_setup.md](05_Phase2_Config/phase2_network_setup.md) | [00_Baseline](04_Evidence/Phase2/00_Baseline/) |
| **Ext A** | Backup `dnsmasq` on `127.0.0.15:53`, dual `/etc/resolver/team1.test`, primary stop failover | [dnsmasq-backup.conf](05_Phase2_Config/dns-backup/dnsmasq-backup.conf) | [Extension_A_Backup_DNS](04_Evidence/Phase2/Extension_A_Backup_DNS/) |
| **Ext B** | `local-ttl=30` verification, `dscacheutil` inspection & manual cache flush | [dnsmasq.conf](02_Config/dnsmasq.conf) | [Extension_B_DNS_TTL](04_Evidence/Phase2/Extension_B_DNS_TTL/) |
| **Ext C** | PF backend isolation anchor (`com.apple/cn_phase2_backend`), rollback & nginx reload | [backend_isolation_anchor.conf](05_Phase2_Config/pf/backend_isolation_anchor.conf) | [Extension_C_Service_Isolation](04_Evidence/Phase2/Extension_C_Service_Isolation/) |
| **Ext D** | HA recovery after `fail_timeout=10s` (`sleep 12`) & round-robin resumption | [nginx_team1.conf](02_Config/nginx_team1.conf) | [Extension_D_HA_Failover](04_Evidence/Phase2/Extension_D_HA_Failover/) |
| **Ext E** | Standby nginx edge (`127.0.0.16`) configuration & DNS cutover workflow | [edge-standby/](05_Phase2_Config/edge-standby/) | [Extension_E_Edge_Migration](04_Evidence/Phase2/Extension_E_Edge_Migration/) |
| **Ext F** | Systematic layer-by-layer troubleshooting methodology (`DNS → TCP → TLS → App`) | [Phase2_Final_Report.md](06_Report/Phase2_Final_Report.md#3-troubleshooting-findings--diagnostic-methodology) | — |

---

## Quick Start (Running Locally on macOS)

```zsh
# 1. Bring up loopback aliases (Phase 1: .11-.14, Phase 2: .15-.16)
for i in 11 12 13 14 15 16; do sudo ifconfig lo0 alias 127.0.0.$i up; done

# 2. Start Backend A and Backend B (in separate terminals)
cd 03_Backend && python3 backend.py A 3001
cd 03_Backend && python3 backend.py B 3002

# 3. Start Primary DNS & Primary Edge
sudo brew services start dnsmasq
sudo brew services start nginx

# 4. (Phase 2 Ext A) Start Backup DNS on 127.0.0.15
sudo dnsmasq --no-daemon --conf-file="$(pwd)/05_Phase2_Config/dns-backup/dnsmasq-backup.conf"

# 5. Verify DNS, TLS, and Load Balancing
dig @127.0.0.11 app.team1.test +short
dig @127.0.0.15 app.team1.test +short
for i in 1 2 3 4 5 6; do curl -sS -D - https://app.team1.test/api/status -o /dev/null | grep -i '^X-Backend:'; done
```

---

## Security Note

Private TLS keys (`*.key`, `*.pem`) are excluded via [`.gitignore`](.gitignore) and are never committed to GitHub.
