"""Database configuration and multi-backend support."""

import os
import logging
from typing import Optional, Dict, Any
from pathlib import Path

log = logging.getLogger(__name__)


class DatabaseConfig:
    """Configuration for database connections."""
    
    def __init__(self, workspace_id: str, db_type: Optional[str] = None):
        self.workspace_id = workspace_id
        self.db_type = db_type or self._detect_db_type()
        
    def _detect_db_type(self) -> str:
        """Detect database type from environment or default to sqlite."""
        db_type = os.getenv("CONPORT_DB_TYPE", "sqlite").lower()
        if db_type not in ["sqlite", "postgresql", "postgres"]:
            log.warning(f"Unknown database type '{db_type}', defaulting to sqlite")
            return "sqlite"
        # Normalize postgres to postgresql
        if db_type == "postgres":
            db_type = "postgresql"
        return db_type
    
    @property
    def is_sqlite(self) -> bool:
        return self.db_type == "sqlite"
    
    @property
    def is_postgresql(self) -> bool:
        return self.db_type == "postgresql"
    
    def get_connection_url(self) -> str:
        """Get database connection URL."""
        if self.is_sqlite:
            return self._get_sqlite_url()
        elif self.is_postgresql:
            return self._get_postgresql_url()
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")
    
    def _get_sqlite_url(self) -> str:
        """Get SQLite connection URL."""
        from ..core.config import get_database_path
        db_path = get_database_path(self.workspace_id)
        return f"sqlite:///{db_path}"
    
    def _get_postgresql_url(self) -> str:
        """Get PostgreSQL connection URL."""
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "postgres")
        
        # Create a safe database name from workspace_id
        safe_workspace = self.workspace_id.replace('/', '_').replace('\\', '_').replace('-', '_')
        db_name = os.getenv("POSTGRES_DB", f"context_portal_{safe_workspace}")
        
        return f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
    
    def get_engine_options(self) -> Dict[str, Any]:
        """Get engine-specific options."""
        if self.is_sqlite:
            return {
                "pool_timeout": 20,
                "pool_recycle": -1,
                "pool_pre_ping": True,
            }
        elif self.is_postgresql:
            return {
                "pool_size": 5,
                "max_overflow": 10,
                "pool_timeout": 30,
                "pool_recycle": 3600,
                "pool_pre_ping": True,
            }
        else:
            return {}


def get_database_config(workspace_id: str, db_type: Optional[str] = None) -> DatabaseConfig:
    """Get database configuration for workspace."""
    return DatabaseConfig(workspace_id, db_type)