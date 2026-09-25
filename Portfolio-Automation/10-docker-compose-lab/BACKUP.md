# Backup and Recovery Strategy

Data persistence and recovery are critical for production deployments. This document details the procedures for backing up and restoring the Docker Compose stack's state.

## 1. What to Back Up
The following components contain stateful data that must be backed up:
- **PostgreSQL databases:** Critical application data, n8n workflows, and potentially Grafana configurations.
- **MinIO data:** Object storage for uploaded files, invoices, and CSVs.
- **Environment config:** The `.env` file and `secrets/` directory on the host machine.

## 2. PostgreSQL Backup

We use `pg_dumpall` to capture all databases and roles.

### Backup Script
Create a script at `/opt/backup_postgres.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/var/backups/portfolio/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
CONTAINER_NAME="portfolio-postgres" # Adjust if your container name differs

mkdir -p "$BACKUP_DIR"

# Execute dump and compress
docker exec "$CONTAINER_NAME" pg_dumpall -U admin | gzip > "$BACKUP_DIR/backup_$DATE.sql.gz"

# Clean up backups older than 7 days
find "$BACKUP_DIR" -type f -name "backup_*.sql.gz" -mtime +7 -delete

echo "PostgreSQL backup completed: backup_$DATE.sql.gz"
```
Make it executable: `chmod +x /opt/backup_postgres.sh`

### Cron Job
Add to `/etc/cron.d/portfolio-backup` to run at 2:00 AM daily:
```cron
0 2 * * * root /opt/backup_postgres.sh >> /var/log/portfolio_backup.log 2>&1
```

## 3. MinIO Backup

For object storage, we use the MinIO Client (`mc`) to mirror buckets.

```bash
# Inside a backup script
docker run --rm -v /var/backups/portfolio/minio:/backup \
  minio/mc mirror --preserve https://minio.yourdomain.com/mybucket /backup/mybucket
```
Alternatively, configure `mc mirror` to sync directly to an external S3-compatible storage provider.

## 4. Retention Policy

To manage disk space while ensuring point-in-time recovery capabilities:
- **Daily:** Keep backups for the last 7 days.
- **Weekly:** Keep Sunday backups for 4 weeks.
- **Monthly:** Keep the 1st of the month backup for 3 months.

*Note: The script provided in Section 2 currently implements the 7-day daily retention. Weekly and monthly retention requires an expanded shell script or dedicated backup software.*

## 5. Restore Procedure

Follow these steps to restore the PostgreSQL database from a backup archive.

1. **Locate the Backup:** Find the desired `.sql.gz` file in your backup directory.
2. **Stop Application Containers:** Stop services that write to the database (API, Celery, n8n) to prevent corruption during restore.
   ```bash
   docker compose stop api celery n8n
   ```
3. **Drop Existing Data (if necessary):** If you are performing a clean restore, you may need to recreate the database or drop existing schemas.
4. **Restore:**
   ```bash
   gunzip -c /var/backups/portfolio/postgres/backup_20231027_020000.sql.gz | docker exec -i portfolio-postgres psql -U admin postgres
   ```
5. **Restart Services:**
   ```bash
   docker compose start api celery n8n
   ```

## 6. Testing Backups

**A backup is only as good as its restore.**
- Perform a manual restore test in a staging environment at least once a month.
- Verify data integrity by logging into the application, checking n8n workflows, and ensuring MinIO files are accessible.
