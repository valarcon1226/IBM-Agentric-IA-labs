# Deployment Guide

This document provides a comprehensive, step-by-step guide to deploying the Docker Compose Production Lab on a Virtual Private Server (VPS) running Ubuntu 22.04 LTS.

## 1. Prerequisites

Before starting, you need a VPS meeting the following requirements:
- **Recommended Providers:** Hetzner (CX22, ~$6/mo), DigitalOcean ($6/mo), AWS Lightsail ($5/mo)
- **Minimum Specifications:** 2 vCPU, 4GB RAM, 40GB SSD
- **OS:** Ubuntu 22.04 LTS
- **Domain:** A registered domain name with access to its DNS settings.

## 2. Initial Server Setup

Log in to your server as `root` via SSH and perform the initial hardening and setup.

### Create a Deploy User
```bash
# Create user 'deploy' (you will be prompted for a password)
adduser deploy

# Add 'deploy' to the sudo group
usermod -aG sudo deploy
```

### Configure SSH Keys
On your local machine, generate an SSH key if you don't have one:
```bash
ssh-keygen -t ed25519 -C "deploy@yourdomain.com"
ssh-copy-id -i ~/.ssh/id_ed25519.pub deploy@your_server_ip
```

### Disable Root Login and Password Authentication
Log in as the `deploy` user to ensure SSH works, then edit the SSH configuration:
```bash
sudo nano /etc/ssh/sshd_config
```
Update the following lines:
```text
PermitRootLogin no
PasswordAuthentication no
```
Restart SSH service:
```bash
sudo systemctl restart ssh
```
> [!WARNING]
> Test SSH access in a new terminal window before closing your current root session to avoid locking yourself out.

## 3. Install Docker

Install Docker Engine, CLI, Containerd, and the Docker Compose plugin.

```bash
# Update package index and install dependencies
sudo apt update
sudo apt install ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
sudo mkdir -m 0755 -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up the repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker packages
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add deploy user to docker group
sudo usermod -aG docker $USER
```
Log out and log back in to apply the group changes. Verify installation:
```bash
docker run hello-world
```

## 4. Configure Firewall (UFW)

Secure the server by enabling the Uncomplicated Firewall (UFW).

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```
Check status: `sudo ufw status`

## 5. Install Fail2ban

Protect SSH from brute-force attacks.

```bash
sudo apt install fail2ban
```
Create a local configuration:
```bash
sudo nano /etc/fail2ban/jail.local
```
Add the following content:
```ini
[sshd]
enabled = true
port = 22
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600
```
Restart Fail2ban:
```bash
sudo systemctl restart fail2ban
```

## 6. Clone and Configure

Clone the repository and prepare the configuration files.

```bash
git clone https://github.com/your-username/portfolio-automation.git
cd portfolio-automation/10-docker-compose-lab

# Create environment configuration
cp .env.example .env
```
Edit the `.env` file and replace placeholders with real values (domains, emails, etc.).

### Generate Secure Passwords
Generate secure 32-character hex passwords for the database and other services:
```bash
openssl rand -hex 32
```
Use these to populate the `secrets/` directory if you are using Docker secrets, or update `.env` accordingly.

### DNS Configuration
Point the following A records to your VPS IP address in your domain registrar's DNS settings:
- `api.yourdomain.com`
- `grafana.yourdomain.com`
- `n8n.yourdomain.com`
- `traefik.yourdomain.com` (if enabling Traefik dashboard)

## 7. Launch

Start the Docker Compose stack.

```bash
docker compose up -d
```

Verify containers are running:
```bash
docker compose ps
```

Monitor Traefik logs to ensure Let's Encrypt certificates are acquired successfully:
```bash
docker compose logs -f traefik
```

## 8. Post-Deploy Verification

Verify that services are accessible and functional.

1. **API:**
   ```bash
   curl -I https://api.yourdomain.com
   ```
   *Expected: HTTP 200 OK*

2. **Grafana:**
   Navigate to `https://grafana.yourdomain.com` in your browser.

3. **n8n:**
   Navigate to `https://n8n.yourdomain.com` in your browser.
