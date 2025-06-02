#!/usr/bin/env python3
"""Test ORM implementation for Context Portal database."""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Add the src directory to the path
src_path = str(Path(__file__).parent / "src")
sys.path.insert(0, src_path)

from context_portal_mcp.db import models
from context_portal_mcp.db import database


def test_orm_implementation():
    """Test that ORM implementation works correctly."""
    print("=" * 60)
    print("Testing ORM Database Implementation")
    print("=" * 60)
    
    # Create a temporary directory for test database
    temp_dir = tempfile.mkdtemp()
    test_workspace = temp_dir
    
    try:
        # Enable ORM mode
        os.environ["CONPORT_USE_ORM"] = "true"
        
        # Force reload of database module to pick up environment variable
        import importlib
        importlib.reload(database)
        
        print(f"✓ Created test workspace: {test_workspace}")
        print(f"✓ ORM mode enabled")
        
        # Test product context
        print("\nTesting product context with ORM...")
        test_content = {
            "project_name": "ORM Test Project",
            "version": "1.0",
            "description": "Testing ORM implementation"
        }
        
        update_args = models.UpdateContextArgs(
            workspace_id=test_workspace,
            content=test_content
        )
        
        # Update product context
        database.update_product_context(test_workspace, update_args)
        print("✓ Product context updated")
        
        # Retrieve product context
        product_context = database.get_product_context(test_workspace)
        assert product_context.content == test_content
        print("✓ Product context retrieved correctly")
        
        # Test decisions
        print("\nTesting decisions with ORM...")
        decision = models.Decision(
            summary="Test ORM Decision",
            rationale="Testing ORM functionality",
            implementation_details="Use SQLAlchemy for database operations",
            tags=["test", "orm"]
        )
        
        # Log decision
        logged_decision = database.log_decision(test_workspace, decision)
        assert logged_decision.id is not None
        print(f"✓ Decision logged with ID: {logged_decision.id}")
        
        # Retrieve decisions
        decisions = database.get_decisions(test_workspace, limit=10)
        assert len(decisions) == 1
        assert decisions[0].summary == "Test ORM Decision"
        print("✓ Decision retrieved correctly")
        
        # Test custom data
        print("\nTesting custom data with ORM...")
        custom_data = models.CustomData(
            category="test",
            key="orm_test",
            value={"message": "ORM is working", "timestamp": datetime.utcnow().isoformat()}
        )
        
        # Log custom data
        logged_data = database.log_custom_data(test_workspace, custom_data)
        assert logged_data.id is not None
        print(f"✓ Custom data logged with ID: {logged_data.id}")
        
        # Retrieve custom data
        custom_data_list = database.get_custom_data(test_workspace, category="test")
        assert len(custom_data_list) == 1
        assert custom_data_list[0].key == "orm_test"
        print("✓ Custom data retrieved correctly")
        
        print("\n" + "=" * 60)
        print("✓ ALL ORM TESTS PASSED!")
        print("✓ ORM implementation is working correctly")
        print("✓ Multi-database support is ready")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ ORM test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        print(f"✓ Test workspace cleanup completed")
    
    return True


def test_database_type_selection():
    """Test that database type can be selected via environment variable."""
    print("\n" + "=" * 60)
    print("Testing Database Type Selection")
    print("=" * 60)
    
    from context_portal_mcp.db.db_config import get_database_config
    
    # Test default (sqlite)
    config = get_database_config("test_workspace")
    assert config.is_sqlite
    print("✓ Default database type is SQLite")
    
    # Test PostgreSQL
    os.environ["CONPORT_DB_TYPE"] = "postgresql"
    config = get_database_config("test_workspace")
    assert config.is_postgresql
    print("✓ PostgreSQL database type detected")
    
    # Test postgres alias
    os.environ["CONPORT_DB_TYPE"] = "postgres"
    config = get_database_config("test_workspace")
    assert config.is_postgresql
    print("✓ Postgres alias works correctly")
    
    # Reset to default
    os.environ.pop("CONPORT_DB_TYPE", None)
    
    print("✓ Database type selection working correctly")


if __name__ == "__main__":
    try:
        # Test database type selection
        test_database_type_selection()
        
        # Test ORM implementation
        success = test_orm_implementation()
        
        if success:
            print("\n🎉 All tests passed! ORM implementation is ready.")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed.")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)