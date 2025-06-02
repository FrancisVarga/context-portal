# Database ORM Implementation

This implementation adds SQLAlchemy ORM support to Context Portal, providing multi-database compatibility while maintaining full backward compatibility with the existing sqlite3 implementation.

## Features

- **Multi-database support**: SQLite, PostgreSQL
- **Backward compatibility**: Existing sqlite3 code continues to work unchanged
- **Configurable**: Use environment variables to select database type and ORM usage
- **Full feature parity**: All existing functionality preserved

## Database Types Supported

1. **SQLite** (default)
   - File-based database
   - No additional setup required
   - Supports FTS5 for full-text search

2. **PostgreSQL**
   - Full-featured relational database
   - Supports advanced full-text search with GIN indexes
   - Requires PostgreSQL server and psycopg2-binary driver

## Configuration

### Environment Variables

- `CONPORT_USE_ORM`: Enable/disable ORM (default: "true")
- `CONPORT_DB_TYPE`: Database type - "sqlite" or "postgresql" (default: "sqlite")

### PostgreSQL Configuration

When using PostgreSQL, set these environment variables:

- `POSTGRES_HOST`: Database host (default: "localhost")
- `POSTGRES_PORT`: Database port (default: "5432")
- `POSTGRES_DB`: Database name (default: "context_portal_{workspace}")
- `POSTGRES_USER`: Username (default: "postgres")
- `POSTGRES_PASSWORD`: Password (default: "postgres")

## Usage Examples

### Using SQLite (default)

```bash
# Default behavior - uses SQLite with ORM
python your_script.py

# Explicit SQLite with ORM
CONPORT_DB_TYPE=sqlite CONPORT_USE_ORM=true python your_script.py

# Legacy SQLite (no ORM)
CONPORT_USE_ORM=false python your_script.py
```

### Using PostgreSQL

```bash
# Basic PostgreSQL setup
CONPORT_DB_TYPE=postgresql python your_script.py

# PostgreSQL with custom connection
CONPORT_DB_TYPE=postgresql \
POSTGRES_HOST=myserver.com \
POSTGRES_USER=myuser \
POSTGRES_PASSWORD=mypass \
POSTGRES_DB=my_context_db \
python your_script.py
```

## Dependencies

The ORM implementation requires additional packages:

```txt
sqlalchemy>=2.0.0
psycopg2-binary  # For PostgreSQL support
```

These are automatically included in the updated requirements.txt and pyproject.toml.

## Implementation Details

### Architecture

The implementation uses a facade pattern:

1. **database.py**: Main interface (unchanged API)
2. **orm_database.py**: SQLAlchemy ORM implementation
3. **orm_models.py**: SQLAlchemy model definitions
4. **db_config.py**: Database configuration management

### Function Routing

Each function in `database.py` checks the `USE_ORM_IMPL` flag:

```python
def get_product_context(workspace_id: str) -> models.ProductContext:
    if USE_ORM_IMPL:
        return orm_database.get_product_context(workspace_id)
    
    # Legacy sqlite3 implementation continues...
```

### Database Initialization

The ORM automatically:

1. Creates all tables using SQLAlchemy metadata
2. Sets up FTS tables/indexes based on database type
3. Initializes default context entries
4. Handles schema migrations through Alembic

### Full-Text Search

- **SQLite**: Uses FTS5 virtual tables with triggers
- **PostgreSQL**: Uses GIN indexes with tsvector/tsquery

## Migration from sqlite3

No migration is required! The implementation is designed for seamless adoption:

1. **Immediate compatibility**: Existing code works without changes
2. **Gradual adoption**: Enable ORM per environment
3. **Data preservation**: Existing SQLite databases work with ORM
4. **Feature parity**: All existing functionality preserved

## Testing

### Run existing tests (legacy mode)
```bash
CONPORT_USE_ORM=false python tests/test_mcp_handlers_simple.py
```

### Test ORM configuration
```bash
python test_orm_minimal.py
```

### Test with different database types
```bash
# SQLite with ORM
CONPORT_DB_TYPE=sqlite python tests/test_mcp_handlers_simple.py

# PostgreSQL (requires running PostgreSQL server)
CONPORT_DB_TYPE=postgresql python tests/test_mcp_handlers_simple.py
```

## Benefits

1. **Database flexibility**: Easy to switch between SQLite and PostgreSQL
2. **Better performance**: PostgreSQL for high-load scenarios
3. **Advanced features**: Better full-text search, concurrent access
4. **Future-proof**: Easy to add more database types
5. **Type safety**: SQLAlchemy provides better type checking
6. **Maintainability**: ORM reduces boilerplate SQL code

## Backward Compatibility

- All existing function signatures unchanged
- All existing behavior preserved
- Legacy sqlite3 code path maintained
- Existing databases work without modification
- Default configuration maintains current behavior

This implementation provides a smooth migration path to modern ORM-based database access while preserving all existing functionality.