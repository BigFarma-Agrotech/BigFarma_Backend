"""more product categories: grains, vegetables, roots and tubers, legumes, oils, ...

Revision ID: a4f8c2e6d913
Revises: 9c3e5a7b2d81
Create Date: 2026-11-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a4f8c2e6d913'
down_revision: Union[str, Sequence[str], None] = '9c3e5a7b2d81'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enum names, which is what SQLAlchemy stores
NEW_CATEGORIES = (
    'GRAINS', 'VEGETABLES', 'FRUITS', 'ROOTS_TUBERS', 'LEGUMES', 'OILS', 'NUTS_SEEDS',
    'SPICES_HERBS', 'CASH_CROPS', 'PROCESSED', 'POULTRY', 'FISH', 'DAIRY_EGGS',
)


def upgrade() -> None:
    # Only Postgres has a real enum type; SQLite stores the name as text
    if op.get_bind().dialect.name != 'postgresql':
        return
    with op.get_context().autocommit_block():
        for name in NEW_CATEGORIES:
            op.execute(f"ALTER TYPE productcategory ADD VALUE IF NOT EXISTS '{name}'")


def downgrade() -> None:
    # Postgres can't drop enum values; move products back to the old two
    if op.get_bind().dialect.name != 'postgresql':
        return
    livestock = ", ".join(f"'{n}'" for n in ('POULTRY', 'FISH', 'DAIRY_EGGS'))
    op.execute(f"UPDATE products SET category = 'LIVESTOCK' WHERE category::text IN ({livestock})")
    crops = ", ".join(f"'{n}'" for n in NEW_CATEGORIES if n not in ('POULTRY', 'FISH', 'DAIRY_EGGS'))
    op.execute(f"UPDATE products SET category = 'CROP' WHERE category::text IN ({crops})")
