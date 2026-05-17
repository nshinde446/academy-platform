#!/usr/bin/env bash
set -euo pipefail

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-academy}"
DB_USER="${DB_USER:-academy_user}"
S3_BUCKET="${S3_BUCKET:-academy-backups}"
BACKUP_DIR="${BACKUP_DIR:-/tmp/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting database backup..."

pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
  --format=custom --compress=9 \
  -f "${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.dump"

pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
  | gzip > "$BACKUP_FILE"

echo "[$(date)] Backup created: $BACKUP_FILE"

if command -v aws &> /dev/null; then
  aws s3 cp "$BACKUP_FILE" "s3://${S3_BUCKET}/db/${DB_NAME}_${TIMESTAMP}.sql.gz"
  aws s3 cp "${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.dump" \
    "s3://${S3_BUCKET}/db/${DB_NAME}_${TIMESTAMP}.dump"
  echo "[$(date)] Backup uploaded to S3: s3://${S3_BUCKET}/db/"
else
  echo "[$(date)] AWS CLI not found – skipping S3 upload"
fi

if [ -d "${REPORT_DIR:-/app/generated_reports}" ]; then
  if command -v aws &> /dev/null; then
    aws s3 sync "${REPORT_DIR:-/app/generated_reports}" \
      "s3://${S3_BUCKET}/reports/" --delete
    echo "[$(date)] Reports synced to S3"
  fi
fi

find "$BACKUP_DIR" -name "*.sql.gz" -mtime +7 -delete
find "$BACKUP_DIR" -name "*.dump" -mtime +7 -delete
echo "[$(date)] Old backups cleaned up (>7 days)"

echo "[$(date)] Backup complete"
