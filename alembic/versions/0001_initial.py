"""Initial schema"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=255)),
        sa.Column("is_premium", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("src_kind", sa.String(length=16), nullable=False),
        sa.Column("src_url", sa.String(length=2048)),
        sa.Column("src_file_id", sa.String(length=512)),
        sa.Column("params", sa.Text()),
        sa.Column("result_path", sa.String(length=2048)),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])

    op.create_table(
        "files",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("path", sa.String(length=2048)),
        sa.Column("size", sa.Integer()),
        sa.Column("mime", sa.String(length=255)),
        sa.Column("hash", sa.String(length=128)),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_files_job_id", "files", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_files_job_id", table_name="files")
    op.drop_table("files")
    op.drop_index("ix_jobs_created_at", table_name="jobs")
    op.drop_index("ix_jobs_user_id", table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("users")
