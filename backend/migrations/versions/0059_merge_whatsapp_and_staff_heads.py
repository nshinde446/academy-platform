"""merge whatsapp-batches (0056) and staff (0058) heads

Revision ID: 0059
Revises: 0056, 0058
Create Date: 2026-09-13 11:23:48.413720

Two migration chains branched off 0055 in parallel — 0056 (per-batch WhatsApp
selection) and 0057→0058 (staff module) — leaving the tree with two heads, which
made ``alembic upgrade head`` ambiguous and failed the production deploy. This is
an empty merge revision that reunites them into a single head; it applies no
schema changes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0059'
down_revision: Union[str, None] = ('0056', '0058')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
