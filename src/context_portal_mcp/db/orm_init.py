"""Database initialization and setup for ORM database layer."""

import logging
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import orm_models

log = logging.getLogger(__name__)


def init_database(engine, config):
    """Initialize database schema and setup."""
    # Create all tables
    orm_models.Base.metadata.create_all(engine)
    
    # Setup FTS based on database type
    if config.is_sqlite:
        setup_sqlite_fts(engine)
    elif config.is_postgresql:
        setup_postgresql_fts(engine)
    
    # Initialize default context entries if they don't exist
    init_default_contexts(engine)


def setup_sqlite_fts(engine):
    """Setup SQLite FTS5 virtual tables and triggers."""
    try:
        with engine.connect() as conn:
            # Create FTS5 virtual table for decisions
            conn.execute(text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS decisions_fts USING fts5(
                    summary, rationale, implementation_details, tags,
                    content='decisions', content_rowid='id'
                )
            """))
            
            # Create FTS5 virtual table for custom_data
            conn.execute(text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS custom_data_fts USING fts5(
                    category, key, value_text,
                    content='custom_data', content_rowid='id'
                )
            """))
            
            # Create triggers for decisions
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS decisions_fts_insert AFTER INSERT ON decisions BEGIN
                    INSERT INTO decisions_fts(rowid, summary, rationale, implementation_details, tags)
                    VALUES (new.id, new.summary, new.rationale, new.implementation_details, new.tags);
                END
            """))
            
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS decisions_fts_delete AFTER DELETE ON decisions BEGIN
                    DELETE FROM decisions_fts WHERE rowid = old.id;
                END
            """))
            
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS decisions_fts_update AFTER UPDATE ON decisions BEGIN
                    DELETE FROM decisions_fts WHERE rowid = old.id;
                    INSERT INTO decisions_fts(rowid, summary, rationale, implementation_details, tags)
                    VALUES (new.id, new.summary, new.rationale, new.implementation_details, new.tags);
                END
            """))
            
            # Create triggers for custom_data
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS custom_data_fts_insert AFTER INSERT ON custom_data BEGIN
                    INSERT INTO custom_data_fts(rowid, category, key, value_text)
                    VALUES (new.id, new.category, new.key, new.value);
                END
            """))
            
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS custom_data_fts_delete AFTER DELETE ON custom_data BEGIN
                    DELETE FROM custom_data_fts WHERE rowid = old.id;
                END
            """))
            
            conn.execute(text("""
                CREATE TRIGGER IF NOT EXISTS custom_data_fts_update AFTER UPDATE ON custom_data BEGIN
                    DELETE FROM custom_data_fts WHERE rowid = old.id;
                    INSERT INTO custom_data_fts(rowid, category, key, value_text)
                    VALUES (new.id, new.category, new.key, new.value);
                END
            """))
            
            conn.commit()
    except Exception as e:
        log.error(f"Failed to setup SQLite FTS: {e}")


def setup_postgresql_fts(engine):
    """Setup PostgreSQL full-text search indexes."""
    try:
        with engine.connect() as conn:
            # Create GIN index for decisions full-text search
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS decisions_fts_idx ON decisions 
                USING GIN (to_tsvector('english', 
                    COALESCE(summary, '') || ' ' || 
                    COALESCE(rationale, '') || ' ' || 
                    COALESCE(implementation_details, '') || ' ' ||
                    COALESCE(tags::text, '')))
            """))
            
            # Create GIN index for custom_data full-text search
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS custom_data_fts_idx ON custom_data 
                USING GIN (to_tsvector('english', 
                    COALESCE(category, '') || ' ' || 
                    COALESCE(key, '') || ' ' || 
                    COALESCE(value::text, '')))
            """))
            
            conn.commit()
    except Exception as e:
        log.error(f"Failed to setup PostgreSQL FTS: {e}")


def init_default_contexts(engine):
    """Initialize default context entries if they don't exist."""
    try:
        with Session(engine) as session:
            # Check if product_context exists, create if not
            if not session.query(orm_models.ProductContext).filter_by(id=1).first():
                default_product = orm_models.ProductContext(id=1, content={})
                session.add(default_product)
            
            # Check if active_context exists, create if not
            if not session.query(orm_models.ActiveContext).filter_by(id=1).first():
                default_active = orm_models.ActiveContext(id=1, content={})
                session.add(default_active)
            
            session.commit()
    except Exception as e:
        log.error(f"Failed to initialize default contexts: {e}")