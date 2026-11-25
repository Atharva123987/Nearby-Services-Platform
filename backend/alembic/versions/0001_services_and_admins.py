"""services and admins tables, PostGIS extension

Revision ID: 0001
Revises:
Create Date: 2026-11-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from geoalchemy2 import Geography
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

service_category = postgresql.ENUM(
    "hospital", "atm", "shop", "other", name="service_category", create_type=False
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    service_category.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "services",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", service_category, nullable=False),
        sa.Column(
            "location",
            Geography(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("rating", sa.Numeric(2, 1), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "char_length(btrim(name)) BETWEEN 1 AND 200", name="ck_services_name_length"
        ),
        sa.CheckConstraint(
            "rating IS NULL OR (rating >= 0 AND rating <= 5)", name="ck_services_rating_range"
        ),
        sa.CheckConstraint(
            "metadata IS NULL OR jsonb_typeof(metadata) = 'object'",
            name="ck_services_metadata_object",
        ),
    )
    op.create_index("ix_services_location", "services", ["location"], postgresql_using="gist")
    op.create_index("ix_services_category", "services", ["category"])
    op.create_index("ix_services_created_at", "services", ["created_at"])

    op.create_table(
        "admins",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("email = lower(email)", name="ck_admins_email_lowercase"),
    )


def downgrade() -> None:
    op.drop_table("admins")
    op.drop_index("ix_services_created_at", table_name="services")
    op.drop_index("ix_services_category", table_name="services")
    op.drop_index("ix_services_location", table_name="services")
    op.drop_table("services")
    service_category.drop(op.get_bind(), checkfirst=True)
    # The postgis extension is left installed: other objects may depend on it.
