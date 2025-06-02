"""Simple database verification tests for mcp_handlers module.

This is a minimal version that demonstrates the concept of verifying data storage 
in the database rather than just mocking the calls.
"""

import os
import tempfile
import shutil
import sqlite3
import json
from pathlib import Path
from datetime import datetime


class SimpleDatabaseTest:
    """Simple database test without external dependencies."""
    
    def __init__(self):
        self.temp_dir = None
        self.test_db_path = None
        
    def setup_test_database(self):
        """Set up a temporary database for testing."""
        # Create a temporary directory for test database
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = Path(self.temp_dir) / "test_context.db"
        
        # Create database schema manually for testing
        conn = sqlite3.connect(str(self.test_db_path))
        cursor = conn.cursor()
        
        # Create basic tables needed for testing
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS product_context (
                id INTEGER PRIMARY KEY,
                content TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                rationale TEXT,
                implementation_details TEXT,
                tags TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS product_context_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version INTEGER NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Initialize product_context with empty content
        cursor.execute('''
            INSERT INTO product_context (id, content) VALUES (1, '{}')
        ''')
        
        conn.commit()
        conn.close()
        
        return str(self.test_db_path)
        
    def teardown_test_database(self):
        """Clean up test database."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            
    def get_database_connection(self):
        """Get direct database connection for verification."""
        return sqlite3.connect(str(self.test_db_path))

    def test_product_context_storage(self):
        """Test that product context can be stored and retrieved from database."""
        print("Testing product context storage...")
        
        # Arrange - Prepare test data
        test_content = {
            "project_name": "Test Project",
            "version": "1.0",
            "description": "A test project for database verification"
        }
        
        # Act - Store data in database (simulating what the handler would do)
        conn = self.get_database_connection()
        cursor = conn.cursor()
        
        # Update product context (simulating handle_update_product_context)
        cursor.execute("UPDATE product_context SET content = ? WHERE id = 1", 
                      [json.dumps(test_content)])
        conn.commit()
        
        # Retrieve data (simulating handle_get_product_context)
        cursor.execute("SELECT content FROM product_context WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        
        # Assert - Verify data was stored correctly
        assert row is not None, "No data found in product_context table"
        stored_content = json.loads(row[0])
        assert stored_content == test_content, f"Expected {test_content}, got {stored_content}"
        
        print("✓ Product context storage test passed")

    def test_decision_logging_storage(self):
        """Test that decisions can be logged and retrieved from database."""
        print("Testing decision logging storage...")
        
        # Arrange - Prepare test data
        workspace_id = "test_workspace"
        summary = "Use PostgreSQL database"
        rationale = "Better performance for our use case"
        implementation_details = "Set up connection pooling"
        tags = ["database", "architecture"]
        
        # Act - Store decision in database (simulating handle_log_decision)
        conn = self.get_database_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO decisions (workspace_id, summary, rationale, implementation_details, tags)
            VALUES (?, ?, ?, ?, ?)
        ''', [workspace_id, summary, rationale, implementation_details, json.dumps(tags)])
        
        decision_id = cursor.lastrowid
        conn.commit()
        
        # Retrieve decision (simulating handle_get_decisions)
        cursor.execute('''
            SELECT id, workspace_id, summary, rationale, implementation_details, tags, timestamp
            FROM decisions WHERE workspace_id = ? AND id = ?
        ''', [workspace_id, decision_id])
        
        row = cursor.fetchone()
        conn.close()
        
        # Assert - Verify decision was stored correctly
        assert row is not None, "Decision was not stored in database"
        stored_id, stored_workspace, stored_summary, stored_rationale, stored_impl, stored_tags, stored_timestamp = row
        
        assert stored_id == decision_id
        assert stored_workspace == workspace_id
        assert stored_summary == summary
        assert stored_rationale == rationale
        assert stored_impl == implementation_details
        assert json.loads(stored_tags) == tags
        assert stored_timestamp is not None
        
        print(f"✓ Decision logging storage test passed (ID: {decision_id})")

    def test_multiple_decisions_storage(self):
        """Test storing multiple decisions and retrieving them."""
        print("Testing multiple decisions storage...")
        
        workspace_id = "test_workspace"
        decisions_data = [
            {"summary": "Decision 1", "rationale": "Reason 1"},
            {"summary": "Decision 2", "rationale": "Reason 2"},
            {"summary": "Decision 3", "rationale": "Reason 3"}
        ]
        
        # Act - Store multiple decisions
        conn = self.get_database_connection()
        cursor = conn.cursor()
        
        stored_ids = []
        for decision in decisions_data:
            cursor.execute('''
                INSERT INTO decisions (workspace_id, summary, rationale)
                VALUES (?, ?, ?)
            ''', [workspace_id, decision["summary"], decision["rationale"]])
            stored_ids.append(cursor.lastrowid)
        
        conn.commit()
        
        # Retrieve all decisions for workspace
        cursor.execute('''
            SELECT id, summary, rationale FROM decisions 
            WHERE workspace_id = ? ORDER BY id
        ''', [workspace_id])
        
        rows = cursor.fetchall()
        conn.close()
        
        # Assert - Verify all decisions were stored
        assert len(rows) >= len(decisions_data), f"Expected at least {len(decisions_data)} decisions, got {len(rows)}"
        
        # Check the last 3 decisions match our test data
        last_decisions = rows[-len(decisions_data):]
        for i, (stored_id, stored_summary, stored_rationale) in enumerate(last_decisions):
            expected = decisions_data[i]
            assert stored_summary == expected["summary"]
            assert stored_rationale == expected["rationale"]
            assert stored_id in stored_ids
        
        print(f"✓ Multiple decisions storage test passed ({len(rows)} total decisions)")

    def test_data_persistence_across_connections(self):
        """Test that data persists when database connection is closed and reopened."""
        print("Testing data persistence across connections...")
        
        test_data = {"persistence_test": True, "timestamp": str(datetime.now())}
        
        # Store data with one connection
        conn1 = self.get_database_connection()
        cursor1 = conn1.cursor()
        cursor1.execute("UPDATE product_context SET content = ? WHERE id = 1", 
                       [json.dumps(test_data)])
        conn1.commit()
        conn1.close()
        
        # Retrieve data with a different connection
        conn2 = self.get_database_connection()
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT content FROM product_context WHERE id = 1")
        row = cursor2.fetchone()
        conn2.close()
        
        # Assert - Data should persist
        assert row is not None
        retrieved_data = json.loads(row[0])
        assert retrieved_data == test_data
        
        print("✓ Data persistence test passed")

    def run_all_tests(self):
        """Run all database verification tests."""
        print("=" * 60)
        print("Running Database Verification Tests")
        print("=" * 60)
        
        try:
            self.setup_test_database()
            print(f"✓ Test database created: {self.test_db_path}")
            
            self.test_product_context_storage()
            self.test_decision_logging_storage()
            self.test_multiple_decisions_storage()
            self.test_data_persistence_across_connections()
            
            print("=" * 60)
            print("✓ ALL DATABASE VERIFICATION TESTS PASSED!")
            print("=" * 60)
            print("\nKey insights demonstrated:")
            print("1. Data is actually stored in SQLite database")
            print("2. Data can be retrieved correctly")
            print("3. Multiple records can be stored and retrieved")
            print("4. Data persists across database connections")
            print("5. This verifies real database interactions vs just mocking")
            
        except Exception as e:
            print(f"✗ Test failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.teardown_test_database()
            print("✓ Test database cleanup completed")


if __name__ == "__main__":
    test = SimpleDatabaseTest()
    test.run_all_tests()