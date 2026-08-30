#!/usr/bin/env bash
# Daily Postgres backup for academy-prod: gzipped pg_dump, rotated N days,
# optional off-box copy to a Hetzner Storage Box, status recorded to DB + JSON.
set -uo pipefail

REPO=/srv/academy/repo
COMPOSE="docker compose -p academy-prod -f $REPO/infra/compose/docker-compose.prod.yml"
OUT=/srv/academy/backups
KEEP=14
TS=$(date -u +%Y%m%d-%H%M%S)
FILE="$OUT/academy-$TS.sql.gz"
mkdir -p "$OUT"

# Dump → gzip → file. -T: no TTY. Fail-safe on the dump exit status.
if $COMPOSE exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' | gzip -9 > "$FILE"; then
  SIZE=$(stat -c%s "$FILE" 2>/dev/null || echo 0)
else
  SIZE=0
fi

# Guard against a truncated/empty dump.
if [ "${SIZE:-0}" -lt 1000 ]; then
  echo "backup FAILED: dump too small (${SIZE} bytes)" >&2
  rm -f "$FILE"
  STATUS=failed
else
  STATUS=ok
fi

# Rotate: keep the newest $KEEP dumps.
ls -1t "$OUT"/academy-*.sql.gz 2>/dev/null | tail -n +$((KEEP+1)) | xargs -r rm -f

# Off-box copy to Hetzner Storage Box, if configured. /root/.backup-storagebox
# defines STORAGE_BOX_TARGET (e.g. u123@u123.your-storagebox.de:backups/).
OFFBOX=skipped
if [ "$STATUS" = ok ] && [ -f /root/.backup-storagebox ]; then
  . /root/.backup-storagebox
  if rsync -e "ssh -i /root/.ssh/backup_storagebox -o StrictHostKeyChecking=accept-new -p 23" -a "$FILE" "$STORAGE_BOX_TARGET" 2>/dev/null; then
    OFFBOX=ok
  else
    OFFBOX=failed
  fi
fi

KEPT=$(ls -1 "$OUT"/academy-*.sql.gz 2>/dev/null | wc -l | tr -d ' ')

# Host-side manifest.
cat > "$OUT/latest.json" <<JSON
{"timestamp":"$(date -u +%Y-%m-%dT%H:%M:%SZ)","file":"$(basename "$FILE")","size_bytes":${SIZE:-0},"status":"$STATUS","offbox":"$OFFBOX","kept":${KEPT:-0}}
JSON

# Best-effort record into the app DB (table created by an app migration; the
# `|| true` keeps the backup working before that lands).
$COMPOSE exec -T db sh -c "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -c \"INSERT INTO backup_runs (id, created_at, status, size_bytes, offbox, filename) VALUES (gen_random_uuid(), now(), '$STATUS', ${SIZE:-0}, '$OFFBOX', '$(basename "$FILE")')\"" >/dev/null 2>&1 || true

echo "backup $STATUS offbox=$OFFBOX size=${SIZE:-0} kept=${KEPT:-0}"
[ "$STATUS" = ok ]
