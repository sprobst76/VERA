"""backfill null api key scopes

API keys with NULL/empty scopes were previously treated as full admin
access at auth time (D-14). That fallback is being removed in favor of
least-privilege (missing scopes -> read-only). Existing keys relying on
implicit admin access (the Shiftjuggler sync key, which only needs to
create/read shifts) must get an explicit "write" scope before the
fallback changes, or they will lose write access.

Revision ID: l6m7n8o9p0q1
Revises: k5l6m7n8o9p0
Create Date: 2026-07-06 21:00:09.351385

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'l6m7n8o9p0q1'
down_revision: Union[str, None] = 'k5l6m7n8o9p0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    api_keys = sa.table(
        "api_keys",
        sa.column("id", sa.String()),
        sa.column("scopes", sa.JSON()),
    )
    rows = conn.execute(sa.select(api_keys.c.id, api_keys.c.scopes)).fetchall()
    for row in rows:
        if not row.scopes:
            conn.execute(
                api_keys.update()
                .where(api_keys.c.id == row.id)
                .values(scopes=["write"])
            )


def downgrade() -> None:
    pass
