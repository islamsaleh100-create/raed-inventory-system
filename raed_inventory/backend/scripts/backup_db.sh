#!/usr/bin/env bash
# =============================================================================
# backup_db.sh — PostgreSQL backup runner (Raed Inventory System)
#
# الاستخدام (تشغيل يدوي):
#   ./backup_db.sh
#
# الاستخدام (cron — يومياً 3 صباحاً بتوقيت الرياض):
#   0 0 * * * cd /opt/raed/backend && ./scripts/backup_db.sh >> /var/log/raed_backup.log 2>&1
#   # (UTC 00:00 = 03:00 Asia/Riyadh)
#
# متطلبات env:
#   DATABASE_URL           — مثال: postgresql://user:pass@host:5432/raed
#   BACKUP_DIR             — اختياري، default: /var/backups/raed
#   BACKUP_RETENTION_DAYS  — اختياري، default: 30
#   S3_BUCKET              — اختياري — لو موجود يرفع النسخة بعد اكتمالها
#   AWS_REGION             — اختياري — default: me-south-1 (Bahrain)
#
# خطة الاستعادة: راجع RESTORE_PROCEDURE.md
# =============================================================================

set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL is required}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/raed}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
S3_BUCKET="${S3_BUCKET:-}"
AWS_REGION="${AWS_REGION:-me-south-1}"

TIMESTAMP="$(date -u +%Y%m%d_%H%M%SZ)"
BACKUP_FILE="${BACKUP_DIR}/raed_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting backup → ${BACKUP_FILE}"

# 1. pg_dump مضغوط (gzip مع check مبكر على الفشل)
if ! pg_dump --format=plain --no-owner --no-privileges "${DATABASE_URL}" | gzip -9 > "${BACKUP_FILE}"; then
    echo "[ERROR] pg_dump failed — removing incomplete file"
    rm -f "${BACKUP_FILE}"
    exit 1
fi

BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "[OK] Local backup created (${BACKUP_SIZE})"

# 2. Integrity check — gzip test + non-empty
gzip -t "${BACKUP_FILE}" || { echo "[ERROR] backup file is corrupted"; exit 1; }
[ -s "${BACKUP_FILE}" ] || { echo "[ERROR] backup file is empty"; exit 1; }

# 3. رفع على S3 اختياري
if [ -n "${S3_BUCKET}" ]; then
    if command -v aws >/dev/null 2>&1; then
        echo "[INFO] Uploading to s3://${S3_BUCKET}/raed/$(basename "${BACKUP_FILE}")"
        aws s3 cp "${BACKUP_FILE}" "s3://${S3_BUCKET}/raed/$(basename "${BACKUP_FILE}")" \
            --region "${AWS_REGION}" \
            --storage-class STANDARD_IA
        echo "[OK] Uploaded to S3"
    else
        echo "[WARN] aws CLI not installed — skipping S3 upload"
    fi
fi

# 4. Rotation — احذف النسخ الأقدم من N يوم
echo "[INFO] Rotating local backups older than ${BACKUP_RETENTION_DAYS} days"
find "${BACKUP_DIR}" -name "raed_*.sql.gz" -type f -mtime +"${BACKUP_RETENTION_DAYS}" -delete
REMAINING=$(find "${BACKUP_DIR}" -name "raed_*.sql.gz" -type f | wc -l)
echo "[OK] Rotation complete — ${REMAINING} backup(s) retained"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Backup finished successfully"
