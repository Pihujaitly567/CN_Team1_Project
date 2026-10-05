# Network setup (all 4 roles on ONE Mac, using loopback aliases)
for i in 11 12 13 14; do sudo ifconfig lo0 alias 127.0.0.$i up; done

| Role | IP | Service | Port |
|-------------------|------------|----------|---------|
| Mac 1 - DNS | 127.0.0.11 | dnsmasq | 53/udp |
| Mac 2 - Edge + LB | 127.0.0.12 | nginx | 80, 443 |
| Mac 3 - Backend A | 127.0.0.13 | backend | 3001 |
| Mac 4 - Backend B | 127.0.0.14 | backend | 3002 |

The Mac sends *.team1.test queries to 127.0.0.11 via /etc/resolver/team1.test
