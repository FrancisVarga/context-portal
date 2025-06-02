"""ORM-based database layer that maintains compatibility with existing interface."""

from typing import List, Optional

# Import all functions from the specialized modules
from .orm_session import (
    get_session, close_all_connections, close_db_connection
)
from .orm_contexts import (
    get_product_context, update_product_context,
    get_active_context, update_active_context
)
from .orm_decisions import (
    log_decision, get_decisions, search_decisions_fts, delete_decision_by_id
)
from .orm_progress import (
    log_progress, get_progress
)
from .orm_custom_data import (
    log_custom_data, get_custom_data
)

# Import model types for compatibility
from .models import (
    ProductContext, ActiveContext, Decision, ProgressEntry, 
    SystemPattern, CustomData, ContextLink, UpdateContextArgs,
    UpdateProgressArgs, GetItemHistoryArgs
)


# Note: Additional functions would be implemented in their respective modules:
# - update_progress_entry
# - delete_progress_entry_by_id  
# - log_system_pattern
# - get_system_patterns
# - delete_system_pattern_by_id
# - delete_custom_data
# - log_context_link
# - get_context_links
# - search_project_glossary_fts
# - search_custom_data_value_fts
# - get_item_history
# - get_recent_activity_summary_data