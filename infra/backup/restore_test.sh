#!/usr/bin/env bash
set -euo pipefail

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-academy_user}"
S3_BUCKET="${S3_BUCKET:-academy-backups}"
TEST_DB_NAME="${TEST_DB_NAME:-academy_restore_test}"
BACKUP_DIR="${BACKUP_DIR:-/tmp/backups}"

echo "[$(date)] Starting restore validation..."

LATEST_DUMP=$(ls -t "${BACKUP_DIR}"/*.dump 2>/dev/null | head -1)

if [ -z "$LATEST_DUMP" ]; then
  if command -v aws &> /dev/null; then
    LATEST_S3=$(aws s3 ls "s3://${S3_BUCKET}/db/" --recursive \
      | grep '\.dump$' | sort -r | head -1 | awk '{print $4}')
    if [ -n "$LATEST_S3" ]; then
      LATEST_DUMP="${BACKUP_DIR}/restore_test.dump"
      aws s3 cp "s3://${S3_BUCKET}/${LATEST_S3}" "$LATEST_DUMP"
    fi
  fi
fi

if [ -z "$LATEST_DUMP" ]; then
  echo "[$(date)] ERROR: No backup file found"
  exit 1
fi

echo "[$(date)] Using backup: $LATEST_DUMP"

psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
  -c "DROP DATABASE IF EXISTS ${TEST_DB_NAME};"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
  -c "CREATE DATABASE ${TEST_DB_NAME};"

pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" \
  -d "$TEST_DB_NAME" --no-owner --no-acl "$LATEST_DUMP"

echo "[$(date)] Restore complete. Validating data integrity..."

TABLES=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" \
  -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';")
echo "[$(date)] Tables found: $TABLES"

if [ "$TABLES" -lt 10 ]; then
  echo "[$(date)] ERROR: Expected at least 10 tables, found $TABLES"
  psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS ${TEST_DB_NAME};"
  exit 1
fi

USERS=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" \
  -t -c "SELECT count(*) FROM users WHERE is_deleted = false;")
echo "[$(date)] Active users: $USERS"

BRANCHES=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TEST_DB_NAME" \
  -t -c "SELECT count(*) FROM branch WHERE is_deleted = false;")
echo "[$(date)] Active branches: $BRANCHES"

psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
  -c "DROP DATABASE IF EXISTS ${TEST_DB_NAME};"

echo "[$(date)] Restore validation PASSED"
