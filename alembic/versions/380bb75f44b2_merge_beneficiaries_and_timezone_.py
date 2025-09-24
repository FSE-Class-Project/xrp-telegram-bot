"""merge beneficiaries and timezone branches

Revision ID: 380bb75f44b2
Revises: 0697b09d6ad7, a24f8c67e4f3
Create Date: 2025-09-24 09:59:06.532956

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '380bb75f44b2'
down_revision: Union[str, None] = ('0697b09d6ad7', 'a24f8c67e4f3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
