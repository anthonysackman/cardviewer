"""initial_skryfall_schema

Revision ID: f727a9b28c57
Revises:
Create Date: 2026-04-11 19:40:46.070772

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f727a9b28c57"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sets",
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("released_at", sa.Date(), nullable=True),
        sa.Column("set_type", sa.String(), nullable=True),
        sa.Column("icon_svg_uri", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "symbols",
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("svg_uri", sa.String(), nullable=True),
        sa.Column("cmc", sa.Float(), nullable=True),
        sa.Column("colors", postgresql.ARRAY(sa.String()), nullable=True),
        sa.PrimaryKeyConstraint("symbol"),
    )
    op.create_table(
        "cards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("oracle_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("mana_cost", sa.String(), nullable=True),
        sa.Column("cmc", sa.Float(), nullable=False),
        sa.Column("type_line", sa.String(), nullable=False),
        sa.Column("oracle_text", sa.String(), nullable=True),
        sa.Column("flavor_text", sa.String(), nullable=True),
        sa.Column("power", sa.String(), nullable=True),
        sa.Column("toughness", sa.String(), nullable=True),
        sa.Column("loyalty", sa.String(), nullable=True),
        sa.Column("rarity", sa.String(), nullable=False),
        sa.Column("set_code", sa.String(), nullable=False),
        sa.Column("set_name", sa.String(), nullable=False),
        sa.Column("collector_number", sa.String(), nullable=False),
        sa.Column("artist", sa.String(), nullable=False),
        sa.Column("color_identity", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("keywords", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("watermark", sa.String(), nullable=True),
        sa.Column("price_usd", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("price_usd_foil", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("prints_search_uri", sa.String(), nullable=False),
        sa.Column("art_crop_url", sa.String(), nullable=False),
        sa.Column("cached_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["set_code"],
            ["sets.code"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "set_code",
            "collector_number",
            name="uq_cards_set_collector",
        ),
    )
    op.create_index("ix_cards_cached_at", "cards", ["cached_at"], unique=False)
    op.create_index("ix_cards_oracle_id", "cards", ["oracle_id"], unique=False)
    op.create_table(
        "card_images",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("card_id", sa.UUID(), nullable=False),
        sa.Column("local_path", sa.String(), nullable=False),
        sa.Column("cached_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("current_card_id", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["current_card_id"],
            ["cards.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("settings")
    op.drop_table("card_images")
    op.drop_index("ix_cards_oracle_id", table_name="cards")
    op.drop_index("ix_cards_cached_at", table_name="cards")
    op.drop_table("cards")
    op.drop_table("symbols")
    op.drop_table("sets")
