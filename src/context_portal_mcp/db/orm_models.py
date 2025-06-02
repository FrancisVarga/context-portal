"""SQLAlchemy ORM models that mirror the existing database schema."""

import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, 
    JSON, create_engine, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

Base = declarative_base()


class JSONEncodedDict(TypeDecorator):
    """Represents an immutable structure as a json-encoded string."""
    
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = json.loads(value)
        return value


class ProductContext(Base):
    __tablename__ = "product_context"
    
    id = Column(Integer, primary_key=True, default=1)
    content = Column(JSONEncodedDict, nullable=False)


class ActiveContext(Base):
    __tablename__ = "active_context"
    
    id = Column(Integer, primary_key=True, default=1)
    content = Column(JSONEncodedDict, nullable=False)


class Decision(Base):
    __tablename__ = "decisions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    summary = Column(Text, nullable=False)
    rationale = Column(Text)
    implementation_details = Column(Text)
    tags = Column(JSONEncodedDict)


class ProgressEntry(Base):
    __tablename__ = "progress_entries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    parent_id = Column(Integer, ForeignKey('progress_entries.id', ondelete='SET NULL'))
    
    # Self-referential relationship for subtasks
    parent = relationship("ProgressEntry", remote_side=[id])


class SystemPattern(Base):
    __tablename__ = "system_patterns"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    name = Column(Text, unique=True, nullable=False)
    description = Column(Text)
    tags = Column(JSONEncodedDict)


class CustomData(Base):
    __tablename__ = "custom_data"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    category = Column(Text, nullable=False)
    key = Column(Text, nullable=False)
    value = Column(JSONEncodedDict, nullable=False)
    
    __table_args__ = (
        UniqueConstraint('category', 'key', name='uq_custom_data_category_key'),
    )


class ProductContextHistory(Base):
    __tablename__ = "product_context_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    version = Column(Integer, nullable=False)
    content = Column(JSONEncodedDict, nullable=False)
    change_source = Column(Text)


class ActiveContextHistory(Base):
    __tablename__ = "active_context_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    version = Column(Integer, nullable=False)
    content = Column(JSONEncodedDict, nullable=False)
    change_source = Column(Text)


class ContextLink(Base):
    __tablename__ = "context_links"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    workspace_id = Column(Text, nullable=False)
    source_item_type = Column(Text, nullable=False)
    source_item_id = Column(Text, nullable=False)
    target_item_type = Column(Text, nullable=False)
    target_item_id = Column(Text, nullable=False)
    relationship_type = Column(Text, nullable=False)
    description = Column(Text)


# FTS tables - these will be handled differently per database type
# For SQLite, we'll use virtual tables
# For PostgreSQL, we'll use full-text search capabilities

class DecisionsFTS(Base):
    __tablename__ = "decisions_fts"
    
    rowid = Column(Integer, primary_key=True)
    # This will be implemented differently per database backend


class CustomDataFTS(Base):
    __tablename__ = "custom_data_fts"
    
    rowid = Column(Integer, primary_key=True)
    # This will be implemented differently per database backend


# Database engine and session management
_engines = {}
_session_factories = {}


def get_database_url(workspace_id: str, db_type: str = "sqlite") -> str:
    """Generate database URL based on type and workspace."""
    if db_type == "sqlite":
        from ..core.config import get_database_path
        db_path = get_database_path(workspace_id)
        return f"sqlite:///{db_path}"
    elif db_type == "postgresql":
        # For PostgreSQL, use environment variables or default values
        import os
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        db_name = os.getenv("POSTGRES_DB", f"context_portal_{workspace_id.replace('/', '_')}")
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "postgres")
        return f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
    else:
        raise ValueError(f"Unsupported database type: {db_type}")


def get_engine(workspace_id: str, db_type: str = "sqlite"):
    """Get or create database engine for workspace."""
    key = f"{workspace_id}_{db_type}"
    if key not in _engines:
        url = get_database_url(workspace_id, db_type)
        _engines[key] = create_engine(url, echo=False)
    return _engines[key]


def get_session_factory(workspace_id: str, db_type: str = "sqlite"):
    """Get or create session factory for workspace."""
    key = f"{workspace_id}_{db_type}"
    if key not in _session_factories:
        engine = get_engine(workspace_id, db_type)
        _session_factories[key] = sessionmaker(bind=engine)
    return _session_factories[key]


def create_tables(workspace_id: str, db_type: str = "sqlite"):
    """Create all tables for the given workspace and database type."""
    engine = get_engine(workspace_id, db_type)
    Base.metadata.create_all(engine)
    
    # Create FTS tables/indexes based on database type
    if db_type == "sqlite":
        _create_sqlite_fts_tables(engine)
    elif db_type == "postgresql":
        _create_postgresql_fts_indexes(engine)


def _create_sqlite_fts_tables(engine):
    """Create SQLite FTS5 virtual tables."""
    with engine.connect() as conn:
        # Create FTS table for decisions
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS decisions_fts USING fts5(
                summary, rationale, implementation_details, tags,
                content='decisions', content_rowid='id'
            )
        """)
        
        # Create FTS table for custom_data
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS custom_data_fts USING fts5(
                category, key, value_text,
                content='custom_data', content_rowid='id'
            )
        """)
        
        # Create triggers to keep FTS tables in sync
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS decisions_fts_insert AFTER INSERT ON decisions BEGIN
                INSERT INTO decisions_fts(rowid, summary, rationale, implementation_details, tags)
                VALUES (new.id, new.summary, new.rationale, new.implementation_details, new.tags);
            END
        """)
        
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS decisions_fts_delete AFTER DELETE ON decisions BEGIN
                DELETE FROM decisions_fts WHERE rowid = old.id;
            END
        """)
        
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS decisions_fts_update AFTER UPDATE ON decisions BEGIN
                DELETE FROM decisions_fts WHERE rowid = old.id;
                INSERT INTO decisions_fts(rowid, summary, rationale, implementation_details, tags)
                VALUES (new.id, new.summary, new.rationale, new.implementation_details, new.tags);
            END
        """)
        
        # Similar triggers for custom_data
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS custom_data_fts_insert AFTER INSERT ON custom_data BEGIN
                INSERT INTO custom_data_fts(rowid, category, key, value_text)
                VALUES (new.id, new.category, new.key, new.value);
            END
        """)
        
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS custom_data_fts_delete AFTER DELETE ON custom_data BEGIN
                DELETE FROM custom_data_fts WHERE rowid = old.id;
            END
        """)
        
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS custom_data_fts_update AFTER UPDATE ON custom_data BEGIN
                DELETE FROM custom_data_fts WHERE rowid = old.id;
                INSERT INTO custom_data_fts(rowid, category, key, value_text)
                VALUES (new.id, new.category, new.key, new.value);
            END
        """)
        
        conn.commit()


def _create_postgresql_fts_indexes(engine):
    """Create PostgreSQL full-text search indexes."""
    with engine.connect() as conn:
        # Create GIN indexes for full-text search on decisions
        conn.execute("""
            CREATE INDEX IF NOT EXISTS decisions_fts_idx ON decisions 
            USING GIN (to_tsvector('english', 
                COALESCE(summary, '') || ' ' || 
                COALESCE(rationale, '') || ' ' || 
                COALESCE(implementation_details, '') || ' ' ||
                COALESCE(tags::text, '')))
        """)
        
        # Create GIN indexes for custom_data
        conn.execute("""
            CREATE INDEX IF NOT EXISTS custom_data_fts_idx ON custom_data 
            USING GIN (to_tsvector('english', 
                COALESCE(category, '') || ' ' || 
                COALESCE(key, '') || ' ' || 
                COALESCE(value::text, '')))
        """)
        
        conn.commit()