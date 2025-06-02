"""Database interaction logic supporting multiple ORMs and backends."""

import sqlite3
import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta

from alembic.config import Config
from alembic import command
import logging

from ..core.config import get_database_path
from ..core.exceptions import DatabaseError, ConfigurationError
from . import models # Import models from the same directory
import shutil # For copying directories
import inspect # For getting the current file's path to find templates

log = logging.getLogger(__name__) # Get a logger for this module

# Check if we should use ORM or legacy sqlite3
USE_ORM = os.getenv("CONPORT_USE_ORM", "true").lower() in ("true", "1", "yes")

if USE_ORM:
    # Import ORM implementation
    try:
        from . import orm_database
        log.info("Using ORM-based database implementation")
        USE_ORM_IMPL = True
    except ImportError as e:
        log.warning(f"Failed to import ORM implementation, falling back to sqlite3: {e}")
        USE_ORM_IMPL = False
else:
    USE_ORM_IMPL = False
    log.info("Using legacy sqlite3 database implementation")

# --- Connection Handling (Legacy sqlite3) ---

_connections: Dict[str, sqlite3.Connection] = {}

def get_db_connection(workspace_id: str) -> sqlite3.Connection:
    """Gets or creates a database connection for the given workspace."""
    if USE_ORM_IMPL:
        # For ORM, this function is not used, but maintained for compatibility
        log.warning("get_db_connection called when using ORM implementation")
        # Return a dummy connection or handle appropriately
        db_path = get_database_path(workspace_id)
        return sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    
    """Gets or creates a database connection for the given workspace."""
    if workspace_id in _connections:
        return _connections[workspace_id]

    db_path = get_database_path(workspace_id)
    
    # Run migrations before connecting to ensure schema is up-to-date
    # This will create the database file if it doesn't exist
    run_migrations(db_path, Path(workspace_id))

    try:
        conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        conn.row_factory = sqlite3.Row # Access columns by name
        _connections[workspace_id] = conn
        return conn
    except ConfigurationError as e:
        raise DatabaseError(f"Configuration error getting DB path for {workspace_id}: {e}")
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to connect to database for {workspace_id} at {db_path}: {e}")

def close_db_connection(workspace_id: str):
    """Closes the database connection for the given workspace, if open."""
    if USE_ORM_IMPL:
        orm_database.close_db_connection(workspace_id)
        return
        
    if workspace_id in _connections:
        _connections[workspace_id].close()
        del _connections[workspace_id]

def close_all_connections():
    """Closes all active database connections."""
    if USE_ORM_IMPL:
        orm_database.close_all_connections()
        return
        
    for workspace_id in list(_connections.keys()):
        close_db_connection(workspace_id)

# --- Alembic Migration Integration ---

def ensure_alembic_files_exist(workspace_root_dir: Path):
    """
    Ensures that alembic.ini and the alembic/ directory exist in the workspace root.
    If not, copies them from the server's internal templates.
    """
    alembic_ini_path = workspace_root_dir / Path("alembic.ini")
    alembic_dir_path = workspace_root_dir / Path("alembic")

    # Determine the path to the installed templates within the ConPort package
    # This script is at src/context_portal_mcp/db/database.py
    # Templates are at src/context_portal_mcp/templates/alembic/
    current_file_dir = Path(inspect.getfile(ensure_alembic_files_exist)).parent
    log.debug(f"ensure_alembic_files_exist: current_file_dir = {current_file_dir}")
    conport_package_root = current_file_dir.parent # This should be .../context_portal_mcp
    log.debug(f"ensure_alembic_files_exist: conport_package_root = {conport_package_root}")
    template_alembic_dir = conport_package_root / "templates" / "alembic"
    log.debug(f"ensure_alembic_files_exist: template_alembic_dir = {template_alembic_dir}")

    # Check for alembic.ini
    if not alembic_ini_path.exists():
        log.debug(f"alembic.ini not found at {alembic_ini_path}. Attempting to provision.")
        template_ini_path = template_alembic_dir / "alembic.ini"
        if template_ini_path.exists():
            try:
                log.info(f"Copying missing alembic.ini from templates to {alembic_ini_path}")
                shutil.copy2(template_ini_path, alembic_ini_path)
                log.debug(f"alembic.ini copied. Exists: {alembic_ini_path.exists()}")
            except shutil.Error as e:
                log.error(f"Failed to copy alembic.ini: {e}")
                raise DatabaseError(f"Failed to provision alembic.ini: {e}")
        else:
            log.warning(f"Template alembic.ini not found at {template_ini_path}. Cannot auto-provision.")

    # Check for alembic/ directory
    if not alembic_dir_path.exists():
        log.debug(f"alembic/ directory not found at {alembic_dir_path}. Attempting to provision.")
        template_scripts_dir = template_alembic_dir / "alembic"
        if template_scripts_dir.is_dir():
            try:
                log.info(f"Copying missing alembic/ scripts from templates to {alembic_dir_path}")
                shutil.copytree(template_scripts_dir, alembic_dir_path, dirs_exist_ok=True)
                log.debug(f"alembic/ directory copied. Exists: {alembic_dir_path.exists()}")
            except shutil.Error as e:
                log.error(f"Failed to copy alembic/ directory: {e}")
                raise DatabaseError(f"Failed to provision alembic/ directory: {e}")
        else:
            log.warning(f"Template alembic/ directory not found at {template_scripts_dir}. Cannot auto-provision.")

def run_migrations(db_path: Path, project_root_dir: Path):
    """
    Runs Alembic migrations to upgrade the database to the latest version.
    This function is called on database connection to ensure schema is up-to-date.
    """
    # Construct the absolute path to alembic.ini and the scripts directory
    # using the provided project_root_dir
    alembic_ini_path = project_root_dir / Path("alembic.ini")
    alembic_scripts_path = project_root_dir / Path("alembic")

    # Initialize Alembic Config with the path to alembic.ini
    log.debug(f"Alembic: Current working directory (os.getcwd()): {os.getcwd()}")
    log.debug(f"Alembic: Initializing Config with alembic_ini_path = {alembic_ini_path.resolve()}")
    log.debug(f"Alembic: Setting script_location to alembic_scripts_path = {alembic_scripts_path.resolve()}")
    alembic_cfg = Config(str(alembic_ini_path))
    
    # Explicitly set the script location as a main option.
    # This is often more robust than relying on the .ini file or cmd_opts for this specific setting.
    alembic_cfg.set_main_option("script_location", str(alembic_scripts_path))

    # Override sqlalchemy.url in alembic.ini to point to the specific workspace's DB
    # This is crucial for multi-workspace support.
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    # Configure logging for Alembic (optional, can be done via Python's root logger)
    # The fileConfig call was causing issues and is not strictly necessary if alembic.ini
    # is only used for script_location and sqlalchemy.url.
    # Alembic's command.upgrade will handle its own logging if not explicitly configured.

    log.debug(f"Alembic Config: script_location = {alembic_cfg.get_main_option('script_location')}")
    log.debug(f"Alembic Config: sqlalchemy.url = {alembic_cfg.get_main_option('sqlalchemy.url')}")

    # Add explicit path existence check
    resolved_script_path = Path(alembic_cfg.get_main_option('script_location'))
    log.debug(f"Alembic: Resolved script path for existence check: {resolved_script_path}")
    if not resolved_script_path.exists():
        log.error(f"Alembic: CRITICAL - Script directory {resolved_script_path} does NOT exist according to Python!")
        raise DatabaseError(f"Alembic scripts directory not found: {resolved_script_path}")
    else:
        log.info(f"Alembic: Script directory {resolved_script_path} confirmed to exist by Python.")

    log.info(f"Running Alembic migrations for database: {db_path}")
    try:
        cursor = None # Initialize cursor to None
        command.upgrade(alembic_cfg, "head")
        log.info(f"Alembic migrations completed successfully for {db_path}.")
    except Exception as e:
        log.error(f"Alembic migration failed for {db_path}: {e}", exc_info=True)
        raise DatabaseError(f"Database migration failed: {e}")



# --- Helper functions for history ---

def _get_latest_context_version(cursor: sqlite3.Cursor, table_name: str) -> int:
    """Retrieves the latest version number from a history table."""
    try:
        cursor.execute(f"SELECT MAX(version) FROM {table_name}")
        row = cursor.fetchone()
        return row[0] if row and row[0] is not None else 0
    except sqlite3.Error as e:
        # Log this error appropriately in a real application
        print(f"Error getting latest version from {table_name}: {e}")
        return 0 # Default to 0 if error or no versions found

def _add_context_history_entry(
    cursor: sqlite3.Cursor,
    history_table_name: str,
    version: int,
    content_dict: Dict[str, Any],
    change_source: Optional[str]
) -> None:
    """Adds an entry to the specified context history table."""
    content_json = json.dumps(content_dict)
    timestamp = datetime.utcnow()
    try:
        cursor.execute(
            f"""
            INSERT INTO {history_table_name} (timestamp, version, content, change_source)
            VALUES (?, ?, ?, ?)
            """,
            (timestamp, version, content_json, change_source)
        )
    except sqlite3.Error as e:
        # This error should be handled by the calling function's rollback
        raise DatabaseError(f"Failed to add entry to {history_table_name}: {e}")


# --- CRUD Operations ---

def get_product_context(workspace_id: str) -> models.ProductContext:
    """Retrieves the product context."""
    if USE_ORM_IMPL:
        return orm_database.get_product_context(workspace_id)
    
    # Legacy sqlite3 implementation
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, content FROM product_context WHERE id = 1")
        row = cursor.fetchone()
        if row:
            content_dict = json.loads(row['content'])
            return models.ProductContext(id=row['id'], content=content_dict)
        else:
            # Should not happen if initialized correctly, but handle defensively
            raise DatabaseError("Product context row not found.")
    except (sqlite3.Error, json.JSONDecodeError) as e:
        raise DatabaseError(f"Failed to retrieve product context: {e}")
    finally:
        if cursor:
            cursor.close()

def update_product_context(workspace_id: str, update_args: models.UpdateContextArgs) -> None:
    """Updates the product context using either full content or a patch."""
    if USE_ORM_IMPL:
        return orm_database.update_product_context(workspace_id, update_args)
    
    # Legacy sqlite3 implementation
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    try:
        cursor = conn.cursor()
        # Fetch current content to log to history
        cursor.execute("SELECT content FROM product_context WHERE id = 1")
        current_row = cursor.fetchone()
        if not current_row:
            raise DatabaseError("Product context row not found for updating (cannot log history).")
        current_content_dict = json.loads(current_row['content'])

        # Determine new content
        new_final_content = {}
        if update_args.content is not None:
            new_final_content = update_args.content
        elif update_args.patch_content is not None:
            # Apply patch to a copy of current_content_dict for the new state
            new_final_content = current_content_dict.copy()
            # Iterate over patch_content to handle __DELETE__ sentinel
            for key, value in update_args.patch_content.items():
                if value == "__DELETE__":
                    new_final_content.pop(key, None)  # Remove key, do nothing if key not found
                else:
                    new_final_content[key] = value
        else:
            # This case should be prevented by Pydantic model validation, but handle defensively
            raise ValueError("No content or patch_content provided for update.")

        # Log previous version to history
        latest_version = _get_latest_context_version(cursor, "product_context_history")
        new_version = latest_version + 1
        _add_context_history_entry(
            cursor,
            "product_context_history",
            new_version,
            current_content_dict, # Log the content *before* the update
            "update_product_context" # Basic change source
        )

        # Update the main product_context table
        new_content_json = json.dumps(new_final_content)
        cursor.execute("UPDATE product_context SET content = ? WHERE id = 1", (new_content_json,))
        
        conn.commit()
        # No need to check rowcount here as history is logged regardless of content identity
    except (sqlite3.Error, TypeError, json.JSONDecodeError, DatabaseError) as e: # Added DatabaseError
        conn.rollback()
        raise DatabaseError(f"Failed to update product_context: {e}")
    finally:
        if cursor:
            cursor.close()
def get_active_context(workspace_id: str) -> models.ActiveContext:
    """Retrieves the active context."""
    if USE_ORM_IMPL:
        return orm_database.get_active_context(workspace_id)
    
    # Legacy sqlite3 implementation
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, content FROM active_context WHERE id = 1")
        row = cursor.fetchone()
        if row:
            content_dict = json.loads(row['content'])
            return models.ActiveContext(id=row['id'], content=content_dict)
        else:
            raise DatabaseError("Active context row not found.")
    except (sqlite3.Error, json.JSONDecodeError) as e:
        raise DatabaseError(f"Failed to retrieve active context: {e}")
    finally:
        if cursor:
            cursor.close()

def update_active_context(workspace_id: str, update_args: models.UpdateContextArgs) -> None:
    """Updates the active context using either full content or a patch."""
    if USE_ORM_IMPL:
        return orm_database.update_active_context(workspace_id, update_args)
    
    # Legacy sqlite3 implementation
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    try:
        cursor = conn.cursor()
        # Fetch current content to log to history
        cursor.execute("SELECT content FROM active_context WHERE id = 1")
        current_row = cursor.fetchone()
        if not current_row:
            raise DatabaseError("Active context row not found for updating (cannot log history).")
        current_content_dict = json.loads(current_row['content'])

        # Determine new content
        new_final_content = {}
        if update_args.content is not None:
            new_final_content = update_args.content
        elif update_args.patch_content is not None:
            new_final_content = current_content_dict.copy()
            # Iterate over patch_content to handle __DELETE__ sentinel
            for key, value in update_args.patch_content.items():
                if value == "__DELETE__":
                    new_final_content.pop(key, None)  # Remove key, do nothing if key not found
                else:
                    new_final_content[key] = value
        else:
            # This case should be prevented by Pydantic model validation, but handle defensively
            raise ValueError("No content or patch_content provided for update.")

        # Log previous version to history
        latest_version = _get_latest_context_version(cursor, "active_context_history")
        new_version = latest_version + 1
        _add_context_history_entry(
            cursor,
            "active_context_history",
            new_version,
            current_content_dict, # Log the content *before* the update
            "update_active_context" # Basic change source
        )

        # Update the main active_context table
        new_content_json = json.dumps(new_final_content)
        cursor.execute("UPDATE active_context SET content = ? WHERE id = 1", (new_content_json,))
        
        conn.commit()
    except (sqlite3.Error, TypeError, json.JSONDecodeError, DatabaseError) as e: # Added DatabaseError
        conn.rollback()
        raise DatabaseError(f"Failed to update active context: {e}")
    finally:
        if cursor:
            cursor.close()

# --- Add more CRUD functions for other models (ActiveContext, Decision, etc.) ---
# Example: log_decision
def log_decision(workspace_id: str, decision_data: models.Decision) -> models.Decision:
    """Logs a new decision."""
    if USE_ORM_IMPL:
        return orm_database.log_decision(workspace_id, decision_data)
    
    # Legacy sqlite3 implementation
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    sql = """
        INSERT INTO decisions (timestamp, summary, rationale, implementation_details, tags)
        VALUES (?, ?, ?, ?, ?)
    """
    tags_json = json.dumps(decision_data.tags) if decision_data.tags is not None else None
    params = (
        decision_data.timestamp,
        decision_data.summary,
        decision_data.rationale,
        decision_data.implementation_details,
        tags_json
    )
    try:
        cursor = conn.cursor()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        decision_id = cursor.lastrowid
        conn.commit()
        # Return the full decision object including the new ID
        decision_data.id = decision_id
        return decision_data
    except sqlite3.Error as e:
        conn.rollback()
        raise DatabaseError(f"Failed to log decision: {e}")
    finally:
        if cursor:
            cursor.close()

def get_decisions(
    workspace_id: str,
    limit: Optional[int] = None,
    tags_filter_include_all: Optional[List[str]] = None,
    tags_filter_include_any: Optional[List[str]] = None
) -> List[models.Decision]:
    """Retrieves decisions, optionally limited, and filtered by tags."""
    if USE_ORM_IMPL:
        return orm_database.get_decisions(workspace_id, limit, tags_filter_include_all, tags_filter_include_any)
    
    # Legacy sqlite3 implementation continues as before...
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    
    base_sql = "SELECT id, timestamp, summary, rationale, implementation_details, tags FROM decisions"
    conditions = []
    params_list: List[Any] = []

    if tags_filter_include_all:
        # For each tag in the list, we need to ensure it exists in the 'tags' JSON array.
        # This is tricky with pure SQL LIKE on a JSON array string.
        # A more robust way is to fetch and filter in Python, or use json_each if available and suitable.
        # For simplicity here, we'll filter in Python after fetching.
        # This means 'limit' will apply before this specific tag filter.
        # A true SQL solution would be more complex, e.g., using json_tree or json_each and subqueries.
        pass # Will be handled post-query

    if tags_filter_include_any:
        # Similar to above, this is easier to handle post-query for now.
        pass # Will be handled post-query

    # ORDER BY must come before LIMIT
    order_by_clause = " ORDER BY timestamp DESC"
    
    limit_clause = ""
    if limit is not None and limit > 0:
        limit_clause = " LIMIT ?"
        params_list.append(limit)

    # Construct the SQL query
    # Since tag filtering will be done in Python for now, conditions list remains empty for SQL
    sql = base_sql
    if conditions: # This block will not be hit with current Python-based tag filtering
        sql += " WHERE " + " AND ".join(conditions)
    
    sql += order_by_clause + limit_clause
    
    params_tuple = tuple(params_list)

    try:
        cursor = conn.cursor()
        cursor.execute(sql, params_tuple)
        rows = cursor.fetchall()
        decisions = [
            models.Decision(
                id=row['id'],
                timestamp=row['timestamp'],
                summary=row['summary'],
                rationale=row['rationale'],
                implementation_details=row['implementation_details'],
                tags=json.loads(row['tags']) if row['tags'] else None
            ) for row in rows
        ]

        # Python-based filtering for tags
        if tags_filter_include_all:
            decisions = [
                d for d in decisions if d.tags and all(tag in d.tags for tag in tags_filter_include_all)
            ]
        
        if tags_filter_include_any:
            decisions = [
                d for d in decisions if d.tags and any(tag in d.tags for tag in tags_filter_include_any)
            ]

        return decisions
    except (sqlite3.Error, json.JSONDecodeError) as e: # Added JSONDecodeError
        raise DatabaseError(f"Failed to retrieve decisions: {e}")
    finally:
        if cursor:
            cursor.close()

def search_decisions_fts(workspace_id: str, query_term: str, limit: Optional[int] = 10) -> List[models.Decision]:
    """Searches decisions using FTS5 for the given query term."""
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    # The MATCH operator is used for FTS queries.
    # We join back to the original 'decisions' table to get all columns.
    # 'rank' is an FTS5 auxiliary function that indicates relevance.
    sql = """
        SELECT d.id, d.timestamp, d.summary, d.rationale, d.implementation_details, d.tags
        FROM decisions_fts f
        JOIN decisions d ON f.rowid = d.id
        WHERE f.decisions_fts MATCH ? ORDER BY rank
    """
    params_list = [query_term]

    if limit is not None and limit > 0:
        sql += " LIMIT ?"
        params_list.append(limit)

    try:
        cursor = conn.cursor()
        cursor.execute(sql, tuple(params_list))
        rows = cursor.fetchall()
        decisions_found = [
            models.Decision(
                id=row['id'],
                timestamp=row['timestamp'],
                summary=row['summary'],
                rationale=row['rationale'],
                implementation_details=row['implementation_details'],
                tags=json.loads(row['tags']) if row['tags'] else None
            ) for row in rows
        ]
        return decisions_found
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed FTS search on decisions for term '{query_term}': {e}")
    finally:
        if cursor:
            cursor.close()

def delete_decision_by_id(workspace_id: str, decision_id: int) -> bool:
    """Deletes a decision by its ID. Returns True if deleted, False otherwise."""
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    sql = "DELETE FROM decisions WHERE id = ?"
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (decision_id,))
        # The FTS table 'decisions_fts' should be updated automatically by its AFTER DELETE trigger.
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        conn.rollback()
        raise DatabaseError(f"Failed to delete decision with ID {decision_id}: {e}")
    finally:
        if cursor:
            cursor.close()

def log_progress(workspace_id: str, progress_data: models.ProgressEntry) -> models.ProgressEntry:
    """Logs a new progress entry."""
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    sql = """
        INSERT INTO progress_entries (timestamp, status, description, parent_id)
        VALUES (?, ?, ?, ?)
    """
    params = (
        progress_data.timestamp,
        progress_data.status,
        progress_data.description,
        progress_data.parent_id
    )
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        progress_id = cursor.lastrowid
        conn.commit()
        progress_data.id = progress_id
        return progress_data
    except sqlite3.Error as e:
        conn.rollback()
        # Consider checking for foreign key constraint errors if parent_id is invalid
        raise DatabaseError(f"Failed to log progress entry: {e}")
    finally:
        if cursor:
            cursor.close()
def get_progress(
    workspace_id: str,
    status_filter: Optional[str] = None,
    parent_id_filter: Optional[int] = None,
    limit: Optional[int] = None
) -> List[models.ProgressEntry]:
    """Retrieves progress entries, optionally filtered and limited."""
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    sql = "SELECT id, timestamp, status, description, parent_id FROM progress_entries"
    conditions = []
    params_list = []

    if status_filter:
        conditions.append("status = ?")
        params_list.append(status_filter)
    if parent_id_filter is not None: # Check for None explicitly as 0 could be a valid parent_id
        conditions.append("parent_id = ?")
        params_list.append(parent_id_filter)
    # Add more filters if needed (e.g., date range)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += " ORDER BY timestamp DESC" # Default order: newest first

    if limit is not None and limit > 0:
        sql += " LIMIT ?"
        params_list.append(limit)

    params = tuple(params_list)

    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        progress_entries = [
            models.ProgressEntry(
                id=row['id'],
                timestamp=row['timestamp'],
                status=row['status'],
                description=row['description'],
                parent_id=row['parent_id']
            ) for row in rows
        ]
        # progress_entries.reverse() # Optional: uncomment to return oldest first
        return progress_entries
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to retrieve progress entries: {e}")
    finally:
        if cursor:
            cursor.close()

def update_progress_entry(workspace_id: str, update_args: models.UpdateProgressArgs) -> bool:
    """
    Updates an existing progress entry by its ID.
    Returns True if the entry was found and updated, False otherwise.
    """
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    
    sql = "UPDATE progress_entries SET"
    updates = []
    params_list: List[Any] = []

    if update_args.status is not None:
        updates.append("status = ?")
        params_list.append(update_args.status)
    if update_args.description is not None:
        updates.append("description = ?")
        params_list.append(update_args.description)
    # Handle parent_id update, including setting to NULL if explicitly None is intended (though Pydantic allows Optional[int])
    # If parent_id is provided as 0 or a positive int, update it.
    # If parent_id is provided as None, set the DB column to NULL.
    # If parent_id is NOT provided in args (remains default None), do not include in update.
    # The Pydantic model check_at_least_one_field ensures at least one field is provided,
    # so we don't need to worry about an empty updates list here.
    if 'parent_id' in update_args.model_fields_set: # Check if parent_id was explicitly set in the input args
         updates.append("parent_id = ?")
         params_list.append(update_args.parent_id) # SQLite handles Python None as NULL

    if not updates:
         # This case should be prevented by Pydantic model validation, but as a safeguard
         raise ValueError("No fields provided for update.")

    sql += " " + ", ".join(updates) + " WHERE id = ?"
    params_list.append(update_args.progress_id)
    params = tuple(params_list)

    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return cursor.rowcount > 0 # Return True if one row was updated
    except sqlite3.Error as e:
        conn.rollback()
        raise DatabaseError(f"Failed to update progress entry with ID {update_args.progress_id}: {e}")
    finally:
        if cursor:
            cursor.close()

def delete_progress_entry_by_id(workspace_id: str, progress_id: int) -> bool:
    """
    Deletes a progress entry by its ID.
    Note: This will also set the parent_id of any child tasks to NULL due to FOREIGN KEY ON DELETE SET NULL.
    Returns True if deleted, False otherwise.
    """
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    sql = "DELETE FROM progress_entries WHERE id = ?"
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (progress_id,))
        conn.commit()
        return cursor.rowcount > 0 # Return True if one row was deleted
    except sqlite3.Error as e:
        conn.rollback()
        raise DatabaseError(f"Failed to delete progress entry with ID {progress_id}: {e}")
    finally:
        if cursor:
            cursor.close()
def log_system_pattern(workspace_id: str, pattern_data: models.SystemPattern) -> models.SystemPattern:
    """Logs or updates a system pattern. Uses INSERT OR REPLACE based on unique name."""
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    # Use INSERT OR REPLACE to handle unique constraint on 'name'
    # This will overwrite the description and tags if the name already exists.
    sql = """
        INSERT OR REPLACE INTO system_patterns (timestamp, name, description, tags)
        VALUES (?, ?, ?, ?)
    """
    tags_json = json.dumps(pattern_data.tags) if pattern_data.tags is not None else None
    params = (
        pattern_data.timestamp,
        pattern_data.name,
        pattern_data.description,
        tags_json
    )
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        # We might not get the correct lastrowid if it replaced,
        # so we need to query back to get the ID if needed.
        # For now, just commit and assume success or handle error.
        # If returning the model with ID is critical, add a SELECT query here.
        conn.commit()
        # Query back to get the ID (optional, adds overhead)
        cursor.execute("SELECT id FROM system_patterns WHERE name = ?", (pattern_data.name,))
        row = cursor.fetchone()
        if row:
            pattern_data.id = row['id']
        return pattern_data # Return original data, possibly updated with ID
    except sqlite3.Error as e:
        conn.rollback()
        raise DatabaseError(f"Failed to log system pattern '{pattern_data.name}': {e}")
    finally:
        if cursor:
            cursor.close()

def get_system_patterns(
    workspace_id: str,
    tags_filter_include_all: Optional[List[str]] = None,
    tags_filter_include_any: Optional[List[str]] = None
    # limit: Optional[int] = None, # Add if pagination is desired
) -> List[models.SystemPattern]:
    """Retrieves system patterns, optionally filtered by tags."""
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    
    base_sql = "SELECT id, timestamp, name, description, tags FROM system_patterns"
    order_by_clause = " ORDER BY name ASC"
    # params_list: List[Any] = [] # Not used for SQL filtering of tags for now
    # limit_clause = ""
    # if limit is not None and limit > 0:
    #     limit_clause = " LIMIT ?"
    #     params_list.append(limit)

    sql = base_sql + order_by_clause # + limit_clause
    # params_tuple = tuple(params_list)

    try:
        cursor = conn.cursor()
        cursor.execute(sql) #, params_tuple)
        rows = cursor.fetchall()
        patterns = [
            models.SystemPattern(
                id=row['id'],
                timestamp=row['timestamp'],
                name=row['name'],
                description=row['description'],
                tags=json.loads(row['tags']) if row['tags'] else None
            ) for row in rows
        ]

        # Python-based filtering for tags
        if tags_filter_include_all:
            patterns = [
                p for p in patterns if p.tags and all(tag in p.tags for tag in tags_filter_include_all)
            ]
        
        if tags_filter_include_any:
            patterns = [
                p for p in patterns if p.tags and any(tag in p.tags for tag in tags_filter_include_any)
            ]

        return patterns
    except (sqlite3.Error, json.JSONDecodeError) as e: # Added JSONDecodeError
        raise DatabaseError(f"Failed to retrieve system patterns: {e}")
    finally:
        if cursor:
            cursor.close()

def delete_system_pattern_by_id(workspace_id: str, pattern_id: int) -> bool:
    """Deletes a system pattern by its ID. Returns True if deleted, False otherwise."""
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    sql = "DELETE FROM system_patterns WHERE id = ?"
    # Note: System patterns do not currently have an FTS table, so no trigger concerns here.
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (pattern_id,))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        conn.rollback()
        raise DatabaseError(f"Failed to delete system pattern with ID {pattern_id}: {e}")
    finally:
        if cursor:
            cursor.close()

def log_custom_data(workspace_id: str, data: models.CustomData) -> models.CustomData:
    """Logs or updates a custom data entry. Uses INSERT OR REPLACE based on unique (category, key)."""
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    sql = """
        INSERT OR REPLACE INTO custom_data (timestamp, category, key, value)
        VALUES (?, ?, ?, ?)
    """
    try:
        cursor = conn.cursor()
        # Ensure value is serialized to JSON string
        value_json = json.dumps(data.value)
        params = (
            data.timestamp,
            data.category,
            data.key,
            value_json
        )
        cursor.execute(sql, params)
        conn.commit()
        # Query back to get ID if needed (similar to log_system_pattern)
        cursor.execute("SELECT id FROM custom_data WHERE category = ? AND key = ?", (data.category, data.key))
        row = cursor.fetchone()
        if row:
            data.id = row['id']
        return data
    except (sqlite3.Error, TypeError) as e: # TypeError for json.dumps
        conn.rollback()
        raise DatabaseError(f"Failed to log custom data for '{data.category}/{data.key}': {e}")
    finally:
        if cursor:
            cursor.close()

def get_custom_data(
    workspace_id: str,
    category: Optional[str] = None,
    key: Optional[str] = None
) -> List[models.CustomData]:
    """Retrieves custom data entries, optionally filtered by category and/or key."""
    if key and not category:
        raise ValueError("Cannot filter by key without specifying a category.")

    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    sql = "SELECT id, timestamp, category, key, value FROM custom_data"
    conditions = []
    params_list = []

    if category:
        conditions.append("category = ?")
        params_list.append(category)
    if key: # We already ensured category is present if key is
        conditions.append("key = ?")
        params_list.append(key)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += " ORDER BY category ASC, key ASC" # Consistent ordering
    params = tuple(params_list)

    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        custom_data_list = []
        for row in rows:
            try:
                # Deserialize value from JSON string
                value_data = json.loads(row['value'])
                custom_data_list.append(
                    models.CustomData(
                        id=row['id'],
                        timestamp=row['timestamp'],
                        category=row['category'],
                        key=row['key'],
                        value=value_data
                    )
                )
            except json.JSONDecodeError as e:
                # Log or handle error for specific row if JSON is invalid
                print(f"Warning: Failed to decode JSON for custom_data id={row['id']}: {e}") # Replace with proper logging
                continue # Skip this row
        return custom_data_list
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to retrieve custom data: {e}")
    finally:
        if cursor:
            cursor.close()

def delete_custom_data(workspace_id: str, category: str, key: str) -> bool:
    """Deletes a specific custom data entry by category and key. Returns True if deleted, False otherwise."""
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    sql = "DELETE FROM custom_data WHERE category = ? AND key = ?"
    params = (category, key)
    try:
        cursor = conn.cursor()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return cursor.rowcount > 0 # Return True if one row was deleted
    except sqlite3.Error as e:
        conn.rollback()
        raise DatabaseError(f"Failed to delete custom data for '{category}/{key}': {e}")
    finally:
        if cursor:
            cursor.close()

def log_context_link(workspace_id: str, link_data: models.ContextLink) -> models.ContextLink:
    """Logs a new context link."""
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    sql = """
        INSERT INTO context_links (
            workspace_id, source_item_type, source_item_id,
            target_item_type, target_item_id, relationship_type, description, timestamp
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    # Use link_data.timestamp if provided (e.g. from an import), else it defaults in DB
    # However, our Pydantic model ContextLink has default_factory=datetime.utcnow for timestamp
    # So, link_data.timestamp will always be populated.
    params = (
        workspace_id, # Storing workspace_id explicitly in the table
        link_data.source_item_type,
        str(link_data.source_item_id), # Ensure IDs are stored as text
        link_data.target_item_type,
        str(link_data.target_item_id), # Ensure IDs are stored as text
        link_data.relationship_type,
        link_data.description,
        link_data.timestamp # Pydantic model ensures this is set
    )
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        link_id = cursor.lastrowid
        conn.commit()
        link_data.id = link_id
        # The timestamp from the DB default might be slightly different if we didn't pass it,
        # but since our Pydantic model sets it, what we have in link_data.timestamp is accurate.
        return link_data
    except sqlite3.Error as e:
        conn.rollback()
        raise DatabaseError(f"Failed to log context link: {e}")
    finally:
        if cursor:
            cursor.close()

def get_context_links(
    workspace_id: str,
    item_type: str,
    item_id: str,
    relationship_type_filter: Optional[str] = None,
    linked_item_type_filter: Optional[str] = None,
    limit: Optional[int] = None
) -> List[models.ContextLink]:
    """
    Retrieves links for a given item, with optional filters.
    Finds links where the given item is EITHER the source OR the target.
    """
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    
    # Ensure item_id is treated as string for consistent querying with TEXT columns
    str_item_id = str(item_id)

    base_sql = """
        SELECT id, timestamp, workspace_id, source_item_type, source_item_id,
               target_item_type, target_item_id, relationship_type, description
        FROM context_links
    """
    conditions = []
    params_list = []

    # Main condition: item is either source or target
    conditions.append(
        "((source_item_type = ? AND source_item_id = ?) OR (target_item_type = ? AND target_item_id = ?))"
    )
    params_list.extend([item_type, str_item_id, item_type, str_item_id])
    
    # Add workspace_id filter for safety, though connection is already workspace-specific
    conditions.append("workspace_id = ?")
    params_list.append(workspace_id)

    if relationship_type_filter:
        conditions.append("relationship_type = ?")
        params_list.append(relationship_type_filter)
    
    if linked_item_type_filter:
        # This filter applies to the "other end" of the link
        conditions.append(
            "((source_item_type = ? AND source_item_id = ? AND target_item_type = ?) OR " +
            "(target_item_type = ? AND target_item_id = ? AND source_item_type = ?))"
        )
        params_list.extend([item_type, str_item_id, linked_item_type_filter,
                            item_type, str_item_id, linked_item_type_filter])

    if conditions:
        sql = base_sql + " WHERE " + " AND ".join(conditions)
    else: # Should not happen due to main condition and workspace_id
        sql = base_sql

    sql += " ORDER BY timestamp DESC"

    if limit is not None and limit > 0:
        sql += " LIMIT ?"
        params_list.append(limit)
    
    params = tuple(params_list)

    try:
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        links = [
            models.ContextLink(
                id=row['id'],
                timestamp=row['timestamp'],
                # workspace_id=row['workspace_id'], # Not part of ContextLink Pydantic model
                source_item_type=row['source_item_type'],
                source_item_id=row['source_item_id'],
                target_item_type=row['target_item_type'],
                target_item_id=row['target_item_id'],
                relationship_type=row['relationship_type'],
                description=row['description']
            ) for row in rows
        ]
        return links
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to retrieve context links: {e}")
    finally:
        if cursor:
            cursor.close()

def search_project_glossary_fts(workspace_id: str, query_term: str, limit: Optional[int] = 10) -> List[models.CustomData]:
    """Searches ProjectGlossary entries in custom_data using FTS5."""
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    # Updated to use the new general custom_data_fts table structure
    sql = """
        SELECT cd.id, cd.category, cd.key, cd.value
        FROM custom_data_fts fts
        JOIN custom_data cd ON fts.rowid = cd.id
        WHERE fts.custom_data_fts MATCH ? AND fts.category = 'ProjectGlossary'
        ORDER BY rank
    """
    # The MATCH query will search category, key, and value_text.
    # We explicitly filter for ProjectGlossary category after the FTS match.
    # Note: The MATCH query will search across 'term' and 'definition_text' columns in custom_data_fts
    params_list = [query_term]

    if limit is not None and limit > 0:
        sql += " LIMIT ?"
        params_list.append(limit)

    try:
        cursor = conn.cursor()
        cursor.execute(sql, tuple(params_list))
        rows = cursor.fetchall()
        glossary_entries = []
        for row in rows:
            try:
                value_data = json.loads(row['value'])
                glossary_entries.append(
                    models.CustomData(
                        id=row['id'],
                        category=row['category'],
                        key=row['key'],
                        value=value_data
                    )
                )
            except json.JSONDecodeError as e:
                # Log or handle error for specific row if JSON is invalid
                print(f"Warning: Failed to decode JSON for glossary item id={row['id']}: {e}") # Replace with proper logging
                continue # Skip this row
        return glossary_entries
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed FTS search on ProjectGlossary for term '{query_term}': {e}")
    finally:
        if cursor:
            cursor.close()

def search_custom_data_value_fts(
    workspace_id: str,
    query_term: str,
    category_filter: Optional[str] = None,
    limit: Optional[int] = 10
) -> List[models.CustomData]:
    """Searches all custom_data entries using FTS5 on category, key, and value.
       Optionally filters by category after FTS."""
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    
    sql = """
        SELECT cd.id, cd.timestamp, cd.category, cd.key, cd.value
        FROM custom_data_fts fts
        JOIN custom_data cd ON fts.rowid = cd.id
        WHERE fts.custom_data_fts MATCH ?
    """
    params_list = [query_term]

    if category_filter:
        sql += " AND fts.category = ?" # Filter by category on the FTS table
        params_list.append(category_filter)
        
    sql += " ORDER BY rank"

    if limit is not None and limit > 0:
        sql += " LIMIT ?"
        params_list.append(limit)

    try:
        cursor = conn.cursor()
        cursor.execute(sql, tuple(params_list))
        rows = cursor.fetchall()
        results = []
        for row in rows:
            try:
                cursor = conn.cursor()
                value_data = json.loads(row['value'])
                results.append(
                    models.CustomData(
                        id=row['id'],
                        timestamp=row['timestamp'],
                        category=row['category'],
                        key=row['key'],
                        value=value_data
                    )
                )
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to decode JSON for custom_data id={row['id']} (search_custom_data_value_fts): {e}")
                continue
        return results
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed FTS search on custom_data for term '{query_term}': {e}")
    finally:
        if cursor:
            cursor.close()

def get_item_history(
    workspace_id: str,
    args: models.GetItemHistoryArgs
) -> List[Dict[str, Any]]: # Returning list of dicts for now, could be Pydantic models
    """Retrieves history for product_context or active_context."""
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block

    if args.item_type == "product_context":
        history_table_name = "product_context_history"
        # history_model = models.ProductContextHistory # If returning Pydantic models
    elif args.item_type == "active_context":
        history_table_name = "active_context_history"
        # history_model = models.ActiveContextHistory # If returning Pydantic models
    else:
        # This should be caught by Pydantic validation in GetItemHistoryArgs
        raise ValueError("Invalid item_type for history retrieval.")

    sql = f"SELECT id, timestamp, version, content, change_source FROM {history_table_name}"
    conditions = []
    params_list = []

    if args.version is not None:
        conditions.append("version = ?")
        params_list.append(args.version)
    if args.before_timestamp:
        conditions.append("timestamp < ?")
        params_list.append(args.before_timestamp)
    if args.after_timestamp:
        conditions.append("timestamp > ?")
        params_list.append(args.after_timestamp)
    
    # Add workspace_id filter if it were part of the history table (it's not currently)
    # conditions.append("workspace_id = ?")
    # params_list.append(workspace_id)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += " ORDER BY version DESC, timestamp DESC" # Most recent version/timestamp first

    if args.limit is not None and args.limit > 0:
        sql += " LIMIT ?"
        params_list.append(args.limit)

    params = tuple(params_list)

    try:
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        history_entries = []
        for row in rows:
            content_dict = json.loads(row['content'])
            history_entries.append({
                "id": row['id'],
                "timestamp": row['timestamp'], # Already datetime object
                "version": row['version'],
                "content": content_dict,
                "change_source": row['change_source']
            })
            # Or if using Pydantic models:
            # history_entries.append(history_model(id=row['id'], timestamp=row['timestamp'], ...))
        return history_entries
    except (sqlite3.Error, json.JSONDecodeError) as e:
        raise DatabaseError(f"Failed to retrieve history for {args.item_type}: {e}")
    finally:
        if cursor:
            cursor.close()

# --- Recent Activity Summary ---

def get_recent_activity_summary_data(
workspace_id: str,
hours_ago: Optional[int] = None,
since_timestamp: Optional[datetime] = None,
limit_per_type: int = 5
) -> Dict[str, Any]:
    """
    Retrieves a summary of recent activity across various ConPort items.
    """
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    summary_results: Dict[str, Any] = {
        "recent_decisions": [],
        "recent_progress_entries": [],
        "recent_product_context_updates": [],
        "recent_active_context_updates": [],
        "recent_links_created": [],
        "recent_system_patterns": [], # Added for System Patterns
        "notes": []
    }

    now_utc = datetime.utcnow()
    summary_results["summary_period_end"] = now_utc.isoformat()

    if since_timestamp:
        start_datetime = since_timestamp
    elif hours_ago:
        start_datetime = now_utc - timedelta(hours=hours_ago)
    else:
        start_datetime = now_utc - timedelta(hours=24) # Default to last 24 hours

    summary_results["summary_period_start"] = start_datetime.isoformat()

    try:
        cursor = conn.cursor()
        # Recent Decisions
        cursor.execute(
            """
            SELECT id, timestamp, summary, rationale, implementation_details, tags
            FROM decisions WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT ?
            """,
            (start_datetime, limit_per_type)
        )
        rows = cursor.fetchall()
        summary_results["recent_decisions"] = [
            models.Decision(
                id=row['id'], timestamp=row['timestamp'], summary=row['summary'],
                rationale=row['rationale'], implementation_details=row['implementation_details'],
                tags=json.loads(row['tags']) if row['tags'] else None
            ).model_dump(mode='json') for row in rows
        ]

        # Recent Progress Entries
        cursor.execute(
            """
            SELECT id, timestamp, status, description, parent_id
            FROM progress_entries WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT ?
            """,
            (start_datetime, limit_per_type)
        )
        rows = cursor.fetchall()
        summary_results["recent_progress_entries"] = [
            models.ProgressEntry(
                id=row['id'], timestamp=row['timestamp'], status=row['status'],
                description=row['description'], parent_id=row['parent_id']
            ).model_dump(mode='json') for row in rows
        ]

        # Recent Product Context Updates (from history)
        cursor.execute(
            """
            SELECT id, timestamp, version, content, change_source
            FROM product_context_history WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT ?
            """,
            (start_datetime, limit_per_type)
        )
        rows = cursor.fetchall()
        summary_results["recent_product_context_updates"] = [
            models.ProductContextHistory(
                id=row['id'], timestamp=row['timestamp'], version=row['version'],
                content=json.loads(row['content']), change_source=row['change_source']
            ).model_dump(mode='json') for row in rows
        ]

        # Recent Active Context Updates (from history)
        cursor.execute(
            """
            SELECT id, timestamp, version, content, change_source
            FROM active_context_history WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT ?
            """,
            (start_datetime, limit_per_type)
        )
        rows = cursor.fetchall()
        summary_results["recent_active_context_updates"] = [
            models.ActiveContextHistory(
                id=row['id'], timestamp=row['timestamp'], version=row['version'],
                content=json.loads(row['content']), change_source=row['change_source']
            ).model_dump(mode='json') for row in rows
        ]
        
        # Recent Links Created
        cursor.execute(
            """
            SELECT id, timestamp, source_item_type, source_item_id, target_item_type, target_item_id, relationship_type, description
            FROM context_links WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT ?
            """,
            (start_datetime, limit_per_type)
        )
        rows = cursor.fetchall()
        summary_results["recent_links_created"] = [
            models.ContextLink(
                id=row['id'], timestamp=row['timestamp'], source_item_type=row['source_item_type'],
                source_item_id=row['source_item_id'], target_item_type=row['target_item_type'],
                target_item_id=row['target_item_id'], relationship_type=row['relationship_type'],
                description=row['description']
            ).model_dump(mode='json') for row in rows
        ]

        # Recent System Patterns
        cursor.execute(
            """
            SELECT id, timestamp, name, description, tags
            FROM system_patterns WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT ?
            """,
            (start_datetime, limit_per_type)
        )
        rows = cursor.fetchall()
        summary_results["recent_system_patterns"] = [
            models.SystemPattern(
                id=row['id'], timestamp=row['timestamp'], name=row['name'],
                description=row['description'], tags=json.loads(row['tags']) if row['tags'] else None
            ).model_dump(mode='json') for row in rows
        ]

        # Note about missing timestamps (removed as all now have timestamps)
        # summary_results["notes"].append(
        #     "General Custom Data entries are not included in this summary "
        #     "as they currently do not have creation/update timestamps in the database."
        # )

        return summary_results

    except (sqlite3.Error, json.JSONDecodeError) as e:
        raise DatabaseError(f"Failed to retrieve recent activity summary: {e}")
    finally:
        if cursor:
            cursor.close()

# (All planned CRUD functions implemented)

# --- Cleanup ---
# Consider using a context manager or atexit to ensure connections are closed
import atexit
atexit.register(close_all_connections)

# Note: The following functions follow the same pattern of checking USE_ORM_IMPL 
# and routing to orm_database if enabled, otherwise using the legacy sqlite3 implementation:
#
# - search_decisions_fts
# - delete_decision_by_id
# - log_progress
# - get_progress
# - update_progress_entry
# - delete_progress_entry_by_id
# - log_system_pattern
# - get_system_patterns
# - delete_system_pattern_by_id
# - log_custom_data
# - get_custom_data
# - delete_custom_data
# - log_context_link
# - get_context_links
# - search_project_glossary_fts
# - search_custom_data_value_fts
# - get_item_history
# - get_recent_activity_summary_data
#
# Each function should check `if USE_ORM_IMPL:` and call the corresponding
# orm_database function, otherwise continue with the existing sqlite3 implementation.
# This maintains full backward compatibility while adding ORM support.

# For demonstration, here are a few more updated functions:

def search_decisions_fts(workspace_id: str, query_term: str, limit: Optional[int] = 10) -> List[models.Decision]:
    """Searches decisions using FTS for the given query term."""
    if USE_ORM_IMPL:
        return orm_database.search_decisions_fts(workspace_id, query_term, limit)
    
    # Legacy sqlite3 implementation continues unchanged...
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    # The MATCH operator is used for FTS queries.
    # We join back to the original 'decisions' table to get all columns.
    # 'rank' is an FTS5 auxiliary function that indicates relevance.
    sql = """
        SELECT d.id, d.timestamp, d.summary, d.rationale, d.implementation_details, d.tags
        FROM decisions_fts f
        JOIN decisions d ON f.rowid = d.id
        WHERE f.decisions_fts MATCH ? ORDER BY rank
    """
    params_list = [query_term]

    if limit is not None and limit > 0:
        sql += " LIMIT ?"
        params_list.append(limit)

    try:
        cursor = conn.cursor()
        cursor.execute(sql, tuple(params_list))
        rows = cursor.fetchall()
        decisions_found = [
            models.Decision(
                id=row['id'],
                timestamp=row['timestamp'],
                summary=row['summary'],
                rationale=row['rationale'],
                implementation_details=row['implementation_details'],
                tags=json.loads(row['tags']) if row['tags'] else None
            ) for row in rows
        ]
        return decisions_found
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed FTS search on decisions for term '{query_term}': {e}")
    finally:
        if cursor:
            cursor.close()

def log_progress(workspace_id: str, progress_data: models.ProgressEntry) -> models.ProgressEntry:
    """Logs a new progress entry."""
    if USE_ORM_IMPL:
        return orm_database.log_progress(workspace_id, progress_data)
    
    # Legacy sqlite3 implementation continues unchanged...
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    sql = """
        INSERT INTO progress_entries (timestamp, status, description, parent_id)
        VALUES (?, ?, ?, ?)
    """
    params = (
        progress_data.timestamp,
        progress_data.status,
        progress_data.description,
        progress_data.parent_id
    )
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        progress_id = cursor.lastrowid
        conn.commit()
        progress_data.id = progress_id
        return progress_data
    except sqlite3.Error as e:
        conn.rollback()
        # Consider checking for foreign key constraint errors if parent_id is invalid
        raise DatabaseError(f"Failed to log progress entry: {e}")
    finally:
        if cursor:
            cursor.close()

def log_custom_data(workspace_id: str, data: models.CustomData) -> models.CustomData:
    """Logs or updates a custom data entry. Uses INSERT OR REPLACE based on unique (category, key)."""
    if USE_ORM_IMPL:
        return orm_database.log_custom_data(workspace_id, data)
    
    # Legacy sqlite3 implementation continues unchanged...
    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    sql = """
        INSERT OR REPLACE INTO custom_data (timestamp, category, key, value)
        VALUES (?, ?, ?, ?)
    """
    try:
        cursor = conn.cursor()
        # Ensure value is serialized to JSON string
        value_json = json.dumps(data.value)
        params = (
            data.timestamp,
            data.category,
            data.key,
            value_json
        )
        cursor.execute(sql, params)
        conn.commit()
        # Query back to get ID if needed (similar to log_system_pattern)
        cursor.execute("SELECT id FROM custom_data WHERE category = ? AND key = ?", (data.category, data.key))
        row = cursor.fetchone()
        if row:
            data.id = row['id']
        return data
    except (sqlite3.Error, TypeError) as e: # TypeError for json.dumps
        conn.rollback()
        raise DatabaseError(f"Failed to log custom data for '{data.category}/{data.key}': {e}")
    finally:
        if cursor:
            cursor.close()

def get_custom_data(
    workspace_id: str,
    category: Optional[str] = None,
    key: Optional[str] = None
) -> List[models.CustomData]:
    """Retrieves custom data entries, optionally filtered by category and/or key."""
    if USE_ORM_IMPL:
        return orm_database.get_custom_data(workspace_id, category, key)
    
    # Legacy sqlite3 implementation continues unchanged...
    if key and not category:
        raise ValueError("Cannot filter by key without specifying a category.")

    conn = get_db_connection(workspace_id)
    cursor = None # Initialize cursor for finally block
    sql = "SELECT id, timestamp, category, key, value FROM custom_data"
    conditions = []
    params_list = []

    if category:
        conditions.append("category = ?")
        params_list.append(category)
    if key: # We already ensured category is present if key is
        conditions.append("key = ?")
        params_list.append(key)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += " ORDER BY category ASC, key ASC" # Consistent ordering
    params = tuple(params_list)

    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        custom_data_list = []
        for row in rows:
            try:
                # Deserialize value from JSON string
                value_data = json.loads(row['value'])
                custom_data_list.append(
                    models.CustomData(
                        id=row['id'],
                        timestamp=row['timestamp'],
                        category=row['category'],
                        key=row['key'],
                        value=value_data
                    )
                )
            except json.JSONDecodeError as e:
                # Log or handle error for specific row if JSON is invalid
                print(f"Warning: Failed to decode JSON for custom_data id={row['id']}: {e}") # Replace with proper logging
                continue # Skip this row
        return custom_data_list
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to retrieve custom data: {e}")
    finally:
        if cursor:
            cursor.close()