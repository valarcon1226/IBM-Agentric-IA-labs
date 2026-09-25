# Security Hardening Checklist

This document outlines the security measures implemented in the Docker Compose Production Lab and best practices for maintaining a secure environment.

## 1. SSH Hardening
The VPS server itself must be secured against unauthorized access.
- [x] **Ed25519 keys only:** Use strong cryptographic keys for SSH access.
- [x] **Disable password auth:** Passwords are vulnerable to brute-force attacks. Set `PasswordAuthentication no` in `/etc/ssh/sshd_config`.
- [x] **Disable root login:** Prevent direct root access. Set `PermitRootLogin no`.
- [ ] **Change SSH port (optional):** Moving SSH off port 22 reduces log noise from automated scanners.
- [x] **Rate limit with Fail2ban:** Protect SSH against repeated failed login attempts.

## 2. Docker Security
Containerized applications require specific security considerations.
- [x] **Run as non-root:** Configure Dockerfiles with a `USER` directive to avoid running processes as root inside the container.
- [x] **Docker Secrets:** Use Docker secrets rather than environment variables for injecting passwords and API keys into containers.
- [x] **Read-only docker.sock:** If a container requires access to the Docker daemon (e.g., Traefik), mount `/var/run/docker.sock` as read-only (`:ro`).
- [x] **Pin image versions:** Avoid using the `:latest` tag. Pin to specific versions (e.g., `postgres:15.3-alpine`) for deterministic deployments and fewer unexpected vulnerabilities.
- [ ] **Scan images:** Regularly scan Docker images for known vulnerabilities using tools like [Trivy](https://github.com/aquasecurity/trivy).

## 3. Network Isolation
Isolate services to minimize the blast radius of a potential breach.
- [x] **Dedicated Networks:** Utilize three Docker networks: `frontend` (exposed to Traefik), `backend` (internal application communication), and `db` (database isolation).
- [x] **No Internet for DBs:** Database containers (PostgreSQL, Redis, MinIO backend) are on internal networks and do not publish ports to the host.
- [x] **Single Ingress:** Only Traefik exposes ports (80/443) to the host machine.

## 4. Firewall (UFW)
Restrict network traffic at the host level.
- [x] **Minimal Open Ports:** Only ports 22 (SSH), 80 (HTTP), and 443 (HTTPS) should be open in UFW.
- [ ] **DOCKER_IPTABLES=false:** *Warning:* By default, Docker bypasses UFW by modifying iptables directly. To fix this, you must configure Docker to not manage iptables or use `ufw-docker` wrapper scripts. Proceed with caution as setting `iptables: false` in `daemon.json` breaks Docker networking without manual IP masquerading rules.

## 5. Secrets Management
Handle sensitive data carefully.
- [x] **Git Ignore:** Ensure `.env` and `secrets/` are listed in `.gitignore` and never committed to version control.
- [x] **Rotate Passwords:** Establish a policy to rotate database passwords and API keys quarterly.
- [x] **Secure Generation:** Always generate passwords securely (e.g., `openssl rand -hex 32`).

## 6. SSL/TLS
Encrypt data in transit.
- [x] **Automatic Certificates:** Traefik automatically provisions and renews Let's Encrypt certificates via ACME.
- [x] **HSTS Headers:** Instruct browsers to strictly use HTTPS via Traefik middleware.
- [x] **TLS 1.2+ Minimum:** Configure Traefik to reject older, insecure TLS protocols.

## 7. Updates
Keep the system patched against vulnerabilities.
- [x] **Unattended Upgrades:** Enable `unattended-upgrades` on Ubuntu for automatic installation of security patches.
- [x] **Monthly Docker Updates:** Schedule a monthly maintenance window to review, update, and deploy new Docker image tags.
