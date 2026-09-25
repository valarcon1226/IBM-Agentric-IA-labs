# Troubleshooting Guide

This document covers common issues encountered while operating the Docker Compose stack and provides diagnostic commands and solutions.

## 1. Traefik Issues

**Symptom: 404 Page Not Found on all routes**
- **Cause:** Traefik cannot route the request. Usually due to missing labels, incorrect network attachments, or DNS propagation issues.
- **Diagnosis:**
  - Verify DNS: `dig +short api.yourdomain.com` (should return your VPS IP).
  - Check container labels in `docker-compose.yml`.
  - Check Traefik logs: `docker compose logs traefik`

**Symptom: SSL certificate not issued (Browser shows insecure warning)**
- **Cause:** Let's Encrypt validation failed.
- **Diagnosis:**
  - Check logs: `docker compose logs traefik | grep ACME`
  - Ensure `ACME_EMAIL` is valid in `.env`.
  - Verify ports 80 and 443 are open: `sudo ufw status`.
  - **Rate Limit:** Let's Encrypt limits to 5 duplicate certificates per week. If hit, wait or use the staging environment for testing.

## 2. Database Issues (PostgreSQL)

**Symptom: Connection refused from other containers**
- **Cause:** Service is not on the `db` network, or PostgreSQL is still starting up.
- **Diagnosis:**
  - Check network: `docker inspect <api-container> -f '{{json .NetworkSettings.Networks}}'`
  - Check Postgres logs for initialization status: `docker compose logs postgres`

**Symptom: "role does not exist" or "database does not exist"**
- **Cause:** The `init-db.sh` script did not run during the first startup.
- **Solution:**
  - Remove the database volume and restart (WARNING: Destroys data):
    ```bash
    docker compose down -v postgres
    docker compose up -d postgres
    ```

**Symptom: Slow queries**
- **Diagnosis:** Check active queries:
  ```bash
  docker exec -it portfolio-postgres psql -U admin -c "SELECT * FROM pg_stat_activity;"
  ```
- **Solution:** Analyze query plans and consider adding database indexes.

## 3. Redis Issues

**Symptom: AUTH failed**
- **Cause:** Password mismatch between the application `.env` and the Redis container configuration or command line args.
- **Solution:** Ensure the password matches across the stack and recreate the container.

**Symptom: Memory full (OOM)**
- **Solution:** Update the Redis command in `docker-compose.yml` to set memory limits and eviction policies:
  ```yaml
  command: redis-server --requirepass ${REDIS_PASSWORD} --maxmemory 256mb --maxmemory-policy allkeys-lru
  ```

## 4. Celery Issues

**Symptom: Worker not processing tasks**
- **Cause:** Unable to connect to the Redis broker.
- **Diagnosis:** Check worker logs: `docker compose logs celery`. Verify `CELERY_BROKER_URL`.

**Symptom: Tasks stuck in queue**
- **Diagnosis:** Inspect active tasks:
  ```bash
  docker compose exec api celery -A core.celery_app inspect active
  ```

## 5. n8n Issues

**Symptom: Webhooks not reachable**
- **Cause:** The webhook URL configuration doesn't match the Traefik domain.
- **Solution:** Ensure `WEBHOOK_URL` in the `.env` file correctly reflects `https://n8n.yourdomain.com`.

**Symptom: Database connection error**
- **Cause:** n8n cannot authenticate with PostgreSQL.
- **Solution:** Verify `N8N_DB_PASSWORD` in your `.env` is the same value that existed when the postgres volume was first created (init-db.sh only runs on an empty volume; to re-run it, `docker compose down -v` deletes all data).

## 6. General Docker Issues

**Symptom: Disk full**
- **Cause:** Unused images, stopped containers, and dangling volumes are consuming space.
- **Diagnosis:** `df -h`
- **Solution:** Clean up Docker data.
  > [!WARNING]
  > This removes all stopped containers, unused networks, dangling images, and unused volumes.
  ```bash
  docker system prune -a --volumes
  ```

**Symptom: Container keeps restarting (Crash Loop)**
- **Diagnosis:** Inspect logs to find the startup error:
  ```bash
  docker logs <container_name_or_id>
  ```

**Symptom: Port conflict on host**
- **Cause:** Another process is binding to port 80 or 443 (e.g., Apache, Nginx).
- **Diagnosis:** Identify the process:
  ```bash
  sudo lsof -i :80
  sudo lsof -i :443
  ```
- **Solution:** Stop and disable the conflicting service (e.g., `sudo systemctl disable --now apache2`).
