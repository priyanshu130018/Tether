from collections.abc import Generator
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def create_db_engine(db_url: str | None = None):
    settings = get_settings()
    url = db_url or settings.database_url
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    elif url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    engine_kwargs: dict[str, object] = {
        "pool_pre_ping": True,
    }
    if not url.startswith("sqlite"):
        engine_kwargs.update(
            {
                "pool_size": settings.db_pool_size,
                "max_overflow": settings.db_max_overflow,
                "pool_timeout": settings.db_pool_timeout,
                "pool_recycle": settings.db_pool_recycle,
            }
        )
    return create_engine(url, **engine_kwargs)


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db(engine_instance=None) -> None:
    # Ensure all models are imported before create_all
    import app.models  # noqa: F401

    target_engine = engine_instance or engine
    Base.metadata.create_all(bind=target_engine)

    try:
        with target_engine.begin() as conn:
            inspector = inspect(conn)
            table_names = inspector.get_table_names()

            # Ensure default tenant exists for legacy and backward-compatible operations
            if "tenants" in table_names:
                result = conn.execute(text("SELECT id FROM tenants WHERE slug = 'default-org' LIMIT 1")).fetchone()
                if not result:
                    conn.execute(
                        text("INSERT INTO tenants (id, name, slug) VALUES (1, 'Default Organization', 'default-org')")
                    )
                if conn.dialect.name == "postgresql":
                    try:
                        conn.execute(text("SELECT setval(pg_get_serial_sequence('tenants', 'id'), (SELECT COALESCE(MAX(id), 1) FROM tenants))"))
                    except Exception:
                        pass

            # Targets schema migration
            if "targets" in table_names:
                existing_cols = {c["name"] for c in inspector.get_columns("targets")}
                columns_to_add = [
                    ("tenant_id", "INTEGER REFERENCES tenants(id) ON DELETE CASCADE DEFAULT 1"),
                    ("status", "VARCHAR(20) DEFAULT 'UNKNOWN'"),
                    ("config", "JSON DEFAULT '{}'"),
                    ("last_checked_at", "TIMESTAMP WITH TIME ZONE"),
                    ("next_check_at", "TIMESTAMP WITH TIME ZONE"),
                    ("last_successful_check_at", "TIMESTAMP WITH TIME ZONE"),
                    ("last_failed_check_at", "TIMESTAMP WITH TIME ZONE"),
                    ("consecutive_failures", "INTEGER DEFAULT 0"),
                    ("consecutive_successes", "INTEGER DEFAULT 0"),
                ]
                for col_name, col_type in columns_to_add:
                    if col_name not in existing_cols:
                        conn.execute(text(f"ALTER TABLE targets ADD COLUMN {col_name} {col_type}"))
                conn.execute(text("UPDATE targets SET tenant_id = 1 WHERE tenant_id IS NULL"))

            # Monitoring Results migration
            if "monitoring_results" in table_names:
                existing_cols = {c["name"] for c in inspector.get_columns("monitoring_results")}
                results_columns_to_add = [
                    ("tenant_id", "INTEGER REFERENCES tenants(id) ON DELETE CASCADE DEFAULT 1"),
                    ("error_type", "VARCHAR(80)"),
                    ("protocol", "VARCHAR(20) DEFAULT 'tcp'"),
                    ("status_code", "INTEGER"),
                    ("extra_data", "JSON DEFAULT '{}'"),
                ]
                for col_name, col_type in results_columns_to_add:
                    if col_name not in existing_cols:
                        conn.execute(text(f"ALTER TABLE monitoring_results ADD COLUMN {col_name} {col_type}"))
                conn.execute(text("UPDATE monitoring_results SET tenant_id = 1 WHERE tenant_id IS NULL"))

            # Jobs migration
            if "jobs" in table_names:
                existing_cols = {c["name"] for c in inspector.get_columns("jobs")}
                if "tenant_id" not in existing_cols:
                    conn.execute(text("ALTER TABLE jobs ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE DEFAULT 1"))
                    conn.execute(text("UPDATE jobs SET tenant_id = 1 WHERE tenant_id IS NULL"))

            # Notification Channels migration
            if "notification_channels" in table_names:
                existing_cols = {c["name"] for c in inspector.get_columns("notification_channels")}
                if "tenant_id" not in existing_cols:
                    conn.execute(text("ALTER TABLE notification_channels ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE DEFAULT 1"))
                    conn.execute(text("UPDATE notification_channels SET tenant_id = 1 WHERE tenant_id IS NULL"))

            # Alert Rules migration
            if "alert_rules" in table_names:
                existing_cols = {c["name"] for c in inspector.get_columns("alert_rules")}
                if "tenant_id" not in existing_cols:
                    conn.execute(text("ALTER TABLE alert_rules ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE DEFAULT 1"))
                    conn.execute(text("UPDATE alert_rules SET tenant_id = 1 WHERE tenant_id IS NULL"))

            # Alert Events migration
            if "alert_events" in table_names:
                existing_cols = {c["name"] for c in inspector.get_columns("alert_events")}
                if "tenant_id" not in existing_cols:
                    conn.execute(text("ALTER TABLE alert_events ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE DEFAULT 1"))
                    conn.execute(text("UPDATE alert_events SET tenant_id = 1 WHERE tenant_id IS NULL"))
    except Exception:
        pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
