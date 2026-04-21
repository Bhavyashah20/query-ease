"""Abstract base class for all database connectors."""

from abc import ABC, abstractmethod
from typing import Dict, List, Any


class BaseConnector(ABC):
    """All DB connectors must implement these methods."""

    @property
    @abstractmethod
    def dialect(self) -> str:
        """Return the SQL dialect name: 'postgresql', 'mysql', 'sqlite'."""
        pass

    @abstractmethod
    def get_schema(self) -> Dict[str, List[dict]]:
        """
        Return schema as:
        {
            "table_name": [
                {"name": "col", "type": "int", "nullable": False, "key": "PRI"},
                ...
            ]
        }
        """
        pass

    @abstractmethod
    def execute(self, sql: str):
        """Execute SQL and return (columns, rows, rows_affected)."""
        pass

    def format_schema_for_prompt(self, schema: Dict[str, List[dict]]) -> str:
        """Convert schema dict to a clean string for the LLM prompt."""
        lines = []
        for table, columns in schema.items():
            lines.append(f"Table: {table}")
            for col in columns:
                key_label = ""
                if col["key"] == "PRI":
                    key_label = " [PRIMARY KEY]"
                elif col["key"] == "MUL":
                    key_label = " [FOREIGN KEY]"
                nullable = "" if col["nullable"] else " NOT NULL"
                lines.append(f"  - {col['name']} ({col['type']}){nullable}{key_label}")
            lines.append("")
        return "\n".join(lines)
