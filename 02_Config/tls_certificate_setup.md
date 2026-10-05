# TLS certificate setup (Team 1)
1. Root CA: openssl genrsa 4096 -> CSR -> self-signed (CA:TRUE, 365 days)
2. Server key (2048-bit) + CSR with CN=app.team1.test
3. Server cert signed by the root CA, SAN = app.team1.test, api.team1.test
4. Cert + key copied to /opt/homebrew/etc/nginx/certs/ (nginx terminates TLS)
5. CA trusted on the Mac:
sudo security add-trusted-cert -d -r trustRoot \
-k /Library/Keychains/System.keychain team1-rootCA.pem
6. Private keys (*.key) are NEVER uploaded to GitHub.
