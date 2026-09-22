"""notification_queue.student_id (+ backfill) for delivery-log batch filter

Revision ID: 0061
Revises: 0060
Create Date: 2026-09-22

Denormalises the student a queued message is about onto ``notification_queue``
so the WhatsApp delivery log can be filtered by batch (queue.student_id ->
student_batch_mappings.batch_id). The value was already present inside
``payload_json`` (the event carries it), so historical rows are backfilled by
extracting it from the JSON text — no data is lost and the batch filter works
over all prior sends, not just new ones. Nullable + indexed; rows with no
parseable student_id (or no student) stay NULL.
"""

from alembic import op
import sqlalchemy as sa

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notification_queue",
        sa.Column("student_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_notification_queue_student_id",
        "notification_queue",
        ["student_id"],
    )
    # Backfill from the JSON payload. Only touch rows whose extracted value is a
    # well-formed UUID so a malformed/absent field is left NULL rather than
    # erroring the cast. Postgres-only expression; this migration only ever runs
    # against Postgres (prod + CI), the test suite builds schema via metadata.
    op.execute(
        """
        UPDATE notification_queue
        SET student_id = (payload_json::jsonb ->> 'student_id')::uuid
        WHERE payload_json IS NOT NULL
          AND payload_json ~ '^\\s*[{[]'
          AND (payload_json::jsonb ->> 'student_id') ~
              '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
        """
    )


def downgrade() -> None:
    op.drop_index("ix_notification_queue_student_id", table_name="notification_queue")
    op.drop_column("notification_queue", "student_id")
