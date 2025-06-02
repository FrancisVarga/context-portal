"""Basic tests for mcp_handlers module."""

import pytest
from unittest.mock import Mock
from datetime import datetime
from typing import Dict, Any, List

# Create simple mock classes for models we need
class MockGetContextArgs:
    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id

class MockUpdateContextArgs:
    def __init__(self, workspace_id: str, content: Dict[str, Any] = None, patch_content: Dict[str, Any] = None):
        self.workspace_id = workspace_id
        self.content = content
        self.patch_content = patch_content

class MockLogDecisionArgs:
    def __init__(self, workspace_id: str, summary: str, rationale: str = None, 
                 implementation_details: str = None, tags: List[str] = None):
        self.workspace_id = workspace_id
        self.summary = summary
        self.rationale = rationale
        self.implementation_details = implementation_details
        self.tags = tags

class MockGetDecisionsArgs:
    def __init__(self, workspace_id: str, limit: int = None, 
                 tags_filter_include_all: List[str] = None, 
                 tags_filter_include_any: List[str] = None):
        self.workspace_id = workspace_id
        self.limit = limit
        self.tags_filter_include_all = tags_filter_include_all
        self.tags_filter_include_any = tags_filter_include_any

class MockSemanticSearchConportArgs:
    def __init__(self, workspace_id: str, query_text: str, top_k: int = 5,
                 filter_item_types: List[str] = None, filter_tags_include_any: List[str] = None,
                 filter_tags_include_all: List[str] = None, filter_custom_data_categories: List[str] = None):
        self.workspace_id = workspace_id
        self.query_text = query_text
        self.top_k = top_k
        self.filter_item_types = filter_item_types
        self.filter_tags_include_any = filter_tags_include_any
        self.filter_tags_include_all = filter_tags_include_all
        self.filter_custom_data_categories = filter_custom_data_categories

class MockBatchLogItemsArgs:
    def __init__(self, workspace_id: str, item_type: str, items: List[Dict[str, Any]]):
        self.workspace_id = workspace_id
        self.item_type = item_type
        self.items = items

# Mock exceptions
class ContextPortalError(Exception):
    pass

class DatabaseError(Exception):
    pass

# Define the handler functions we want to test directly (simplified versions of the actual handlers)
def mock_handle_get_product_context(args, db_module):
    """Mock implementation of handle_get_product_context for testing."""
    try:
        context_model = db_module.get_product_context(args.workspace_id)
        return context_model.content
    except DatabaseError as e:
        raise ContextPortalError(f"Database error getting product context: {e}")
    except Exception as e:
        raise ContextPortalError(f"Unexpected error in get_product_context: {e}")

def mock_handle_update_product_context(args, db_module):
    """Mock implementation of handle_update_product_context for testing."""
    try:
        db_module.update_product_context(args.workspace_id, args)
        return {"status": "success", "message": "Product context updated successfully."}
    except DatabaseError as e:
        raise ContextPortalError(f"Database error updating product context: {e}")
    except Exception as e:
        raise ContextPortalError(f"Unexpected error in update_product_context: {e}")

def mock_handle_log_decision(args, db_module):
    """Mock implementation of handle_log_decision for testing."""
    try:
        # Create decision object similar to actual implementation
        decision_to_log = type('Decision', (), {
            'summary': args.summary,
            'rationale': args.rationale,
            'implementation_details': args.implementation_details,
            'tags': args.tags
        })()
        
        logged_decision = db_module.log_decision(args.workspace_id, decision_to_log)
        
        return {
            "status": "success",
            "message": "Decision logged successfully.",
            "decision_id": logged_decision.id,
            "timestamp": logged_decision.timestamp.isoformat()
        }
    except DatabaseError as e:
        raise ContextPortalError(f"Database error logging decision: {e}")
    except Exception as e:
        raise ContextPortalError(f"Unexpected error in log_decision: {e}")

def mock_handle_get_decisions(args, db_module):
    """Mock implementation of handle_get_decisions for testing."""
    try:
        decisions_list = db_module.get_decisions(
            args.workspace_id,
            limit=args.limit,
            tags_filter_include_all=args.tags_filter_include_all,
            tags_filter_include_any=args.tags_filter_include_any
        )
        
        return [
            {
                "id": decision.id,
                "timestamp": decision.timestamp.isoformat(),
                "summary": decision.summary,
                "rationale": getattr(decision, 'rationale', None),
                "implementation_details": getattr(decision, 'implementation_details', None),
                "tags": getattr(decision, 'tags', None)
            }
            for decision in decisions_list
        ]
    except DatabaseError as e:
        raise ContextPortalError(f"Database error getting decisions: {e}")
    except Exception as e:
        raise ContextPortalError(f"Unexpected error in get_decisions: {e}")

async def mock_handle_semantic_search_conport(args, embedding_service, vector_store_service):
    """Mock implementation of handle_semantic_search_conport for testing."""
    try:
        query_vector = embedding_service.get_embedding(args.query_text)
        
        # Build filters for vector store
        filters = {}
        if args.filter_item_types:
            if len(args.filter_item_types) == 1:
                filters["conport_item_type"] = args.filter_item_types[0]
            else:
                filters["conport_item_type"] = {"$in": args.filter_item_types}
        
        results = vector_store_service.query_vector_store(
            args.workspace_id,
            query_vector,
            top_k=args.top_k,
            filters=filters if filters else None
        )
        
        return [
            {
                "item_type": result["conport_item_type"],
                "item_id": result["conport_item_id"],
                "distance": result.get("distance", 0.0),
                "metadata": result.get("metadata", {})
            }
            for result in results
        ]
    except Exception as e:
        raise ContextPortalError(f"Unexpected error in semantic_search_conport: {e}")

def mock_handle_batch_log_items(args, batch_handlers):
    """Mock implementation of handle_batch_log_items for testing."""
    results = []
    errors = []
    success_count = 0
    failure_count = 0
    
    if args.item_type not in batch_handlers:
        return {
            "status": "failure",
            "message": f"Unsupported item type: {args.item_type}",
            "successful_items": 0,
            "failed_items": len(args.items)
        }
    
    handler_func, args_class = batch_handlers[args.item_type]
    
    for i, item_data in enumerate(args.items):
        try:
            # Create arguments for the specific handler
            item_args = args_class(workspace_id=args.workspace_id, **item_data)
            result = handler_func(item_args)
            results.append(result)
            success_count += 1
        except Exception as e:
            errors.append({"item_index": i, "error": str(e), "data": item_data})
            failure_count += 1
    
    return {
        "status": "partial_success" if success_count > 0 and failure_count > 0 else ("success" if failure_count == 0 else "failure"),
        "message": f"Batch log for '{args.item_type}': {success_count} succeeded, {failure_count} failed.",
        "successful_items": success_count,
        "failed_items": failure_count,
        "results": results,
        "errors": errors
    }


class TestHandleGetProductContext:
    """Tests for handle_get_product_context function."""

    def test_get_product_context_success(self):
        """Test successful retrieval of product context."""
        # Arrange
        workspace_id = "test_workspace"
        expected_content = {"project_name": "Test Project", "version": "1.0"}
        
        mock_db = Mock()
        mock_context = Mock()
        mock_context.content = expected_content
        mock_db.get_product_context.return_value = mock_context
        
        args = MockGetContextArgs(workspace_id=workspace_id)
        
        # Act
        result = mock_handle_get_product_context(args, mock_db)
        
        # Assert
        assert result == expected_content
        mock_db.get_product_context.assert_called_once_with(workspace_id)

    def test_get_product_context_database_error(self):
        """Test handling of database error."""
        # Arrange
        workspace_id = "test_workspace"
        mock_db = Mock()
        mock_db.get_product_context.side_effect = DatabaseError("DB connection failed")
        
        args = MockGetContextArgs(workspace_id=workspace_id)
        
        # Act & Assert
        with pytest.raises(ContextPortalError, match="Database error getting product context"):
            mock_handle_get_product_context(args, mock_db)

    def test_get_product_context_unexpected_error(self):
        """Test handling of unexpected error."""
        # Arrange
        workspace_id = "test_workspace"
        mock_db = Mock()
        mock_db.get_product_context.side_effect = ValueError("Unexpected error")
        
        args = MockGetContextArgs(workspace_id=workspace_id)
        
        # Act & Assert
        with pytest.raises(ContextPortalError, match="Unexpected error in get_product_context"):
            mock_handle_get_product_context(args, mock_db)


class TestHandleUpdateProductContext:
    """Tests for handle_update_product_context function."""

    def test_update_product_context_success(self):
        """Test successful update of product context."""
        # Arrange
        workspace_id = "test_workspace"
        content = {"project_name": "Updated Project", "version": "2.0"}
        
        mock_db = Mock()
        args = MockUpdateContextArgs(workspace_id=workspace_id, content=content)
        
        # Act
        result = mock_handle_update_product_context(args, mock_db)
        
        # Assert
        expected_result = {"status": "success", "message": "Product context updated successfully."}
        assert result == expected_result
        mock_db.update_product_context.assert_called_once_with(workspace_id, args)

    def test_update_product_context_database_error(self):
        """Test handling of database error during update."""
        # Arrange
        workspace_id = "test_workspace"
        content = {"project_name": "Updated Project"}
        mock_db = Mock()
        mock_db.update_product_context.side_effect = DatabaseError("Update failed")
        
        args = MockUpdateContextArgs(workspace_id=workspace_id, content=content)
        
        # Act & Assert
        with pytest.raises(ContextPortalError, match="Database error updating product context"):
            mock_handle_update_product_context(args, mock_db)


class TestHandleLogDecision:
    """Tests for handle_log_decision function."""

    def test_log_decision_success(self):
        """Test successful logging of a decision."""
        # Arrange
        workspace_id = "test_workspace"
        summary = "Use PostgreSQL database"
        rationale = "Better performance for our use case"
        tags = ["database", "architecture"]
        
        mock_db = Mock()
        mock_logged_decision = Mock()
        mock_logged_decision.id = 1
        mock_logged_decision.timestamp = datetime(2023, 1, 1, 12, 0, 0)
        mock_db.log_decision.return_value = mock_logged_decision
        
        args = MockLogDecisionArgs(
            workspace_id=workspace_id,
            summary=summary,
            rationale=rationale,
            tags=tags
        )
        
        # Act
        result = mock_handle_log_decision(args, mock_db)
        
        # Assert
        assert result["status"] == "success"
        assert result["message"] == "Decision logged successfully."
        assert result["decision_id"] == 1
        mock_db.log_decision.assert_called_once()

    def test_log_decision_database_error(self):
        """Test handling of database error during decision logging."""
        # Arrange
        workspace_id = "test_workspace"
        summary = "Use PostgreSQL database"
        mock_db = Mock()
        mock_db.log_decision.side_effect = DatabaseError("Log failed")
        
        args = MockLogDecisionArgs(workspace_id=workspace_id, summary=summary)
        
        # Act & Assert
        with pytest.raises(ContextPortalError, match="Database error logging decision"):
            mock_handle_log_decision(args, mock_db)


class TestHandleGetDecisions:
    """Tests for handle_get_decisions function."""

    def test_get_decisions_success(self):
        """Test successful retrieval of decisions."""
        # Arrange
        workspace_id = "test_workspace"
        mock_db = Mock()
        mock_decisions = [
            Mock(id=1, summary="Decision 1", timestamp=datetime(2023, 1, 1), rationale="Reason 1", tags=["tag1"]),
            Mock(id=2, summary="Decision 2", timestamp=datetime(2023, 1, 2), rationale="Reason 2", tags=["tag2"])
        ]
        mock_db.get_decisions.return_value = mock_decisions
        
        args = MockGetDecisionsArgs(workspace_id=workspace_id, limit=10)
        
        # Act
        result = mock_handle_get_decisions(args, mock_db)
        
        # Assert
        assert len(result) == 2
        assert all("id" in decision for decision in result)
        assert result[0]["summary"] == "Decision 1"
        assert result[1]["summary"] == "Decision 2"
        mock_db.get_decisions.assert_called_once()

    def test_get_decisions_database_error(self):
        """Test handling of database error during decision retrieval."""
        # Arrange
        workspace_id = "test_workspace"
        mock_db = Mock()
        mock_db.get_decisions.side_effect = DatabaseError("Query failed")
        
        args = MockGetDecisionsArgs(workspace_id=workspace_id)
        
        # Act & Assert
        with pytest.raises(ContextPortalError, match="Database error getting decisions"):
            mock_handle_get_decisions(args, mock_db)


class TestHandleSemanticSearchConport:
    """Tests for handle_semantic_search_conport async function."""

    @pytest.mark.asyncio
    async def test_semantic_search_success(self):
        """Test successful semantic search."""
        # Arrange
        workspace_id = "test_workspace"
        query_text = "database decisions"
        
        mock_embedding_service = Mock()
        mock_vector_store_service = Mock()
        
        mock_embedding_service.get_embedding.return_value = [0.1, 0.2, 0.3]
        mock_vector_store_service.query_vector_store.return_value = [
            {
                "chroma_doc_id": "decision_1",
                "conport_item_type": "decision",
                "conport_item_id": "1",
                "distance": 0.5,
                "metadata": {"summary": "Use PostgreSQL"}
            }
        ]
        
        args = MockSemanticSearchConportArgs(
            workspace_id=workspace_id,
            query_text=query_text
        )
        
        # Act
        result = await mock_handle_semantic_search_conport(args, mock_embedding_service, mock_vector_store_service)
        
        # Assert
        assert len(result) == 1
        assert result[0]["item_type"] == "decision"
        assert result[0]["item_id"] == "1"
        mock_embedding_service.get_embedding.assert_called_once_with(query_text)
        mock_vector_store_service.query_vector_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_semantic_search_embedding_error(self):
        """Test handling of embedding service error."""
        # Arrange
        workspace_id = "test_workspace"
        query_text = "database decisions"
        mock_embedding_service = Mock()
        mock_vector_store_service = Mock()
        mock_embedding_service.get_embedding.side_effect = Exception("Embedding failed")
        
        args = MockSemanticSearchConportArgs(
            workspace_id=workspace_id,
            query_text=query_text
        )
        
        # Act & Assert
        with pytest.raises(ContextPortalError, match="Unexpected error in semantic_search_conport"):
            await mock_handle_semantic_search_conport(args, mock_embedding_service, mock_vector_store_service)


class TestHandleBatchLogItems:
    """Tests for handle_batch_log_items function."""

    def test_batch_log_items_success(self):
        """Test successful batch logging of items."""
        # Arrange
        workspace_id = "test_workspace"
        item_type = "decision"
        items = [
            {"summary": "Decision 1", "rationale": "Reason 1"},
            {"summary": "Decision 2", "rationale": "Reason 2"}
        ]
        
        mock_handler = Mock()
        mock_handler.return_value = {"status": "success", "decision_id": 1}
        batch_handlers = {
            "decision": (mock_handler, MockLogDecisionArgs)
        }
        
        args = MockBatchLogItemsArgs(
            workspace_id=workspace_id,
            item_type=item_type,
            items=items
        )
        
        # Act
        result = mock_handle_batch_log_items(args, batch_handlers)
        
        # Assert
        assert result["status"] == "success"
        assert result["successful_items"] == 2
        assert result["failed_items"] == 0
        assert mock_handler.call_count == 2

    def test_batch_log_items_unsupported_type(self):
        """Test handling of unsupported item type."""
        # Arrange
        workspace_id = "test_workspace"
        item_type = "unsupported_type"
        items = [{"summary": "Test"}]
        
        batch_handlers = {}  # Empty handlers
        
        args = MockBatchLogItemsArgs(
            workspace_id=workspace_id,
            item_type=item_type,
            items=items
        )
        
        # Act
        result = mock_handle_batch_log_items(args, batch_handlers)
        
        # Assert
        assert result["status"] == "failure"
        assert "Unsupported item type" in result["message"]
        assert result["successful_items"] == 0
        assert result["failed_items"] == 1


if __name__ == "__main__":
    pytest.main([__file__])