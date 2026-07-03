import os
import json
import sys
from fastmcp import FastMCP
from db import SQLiteAdapter, PostgreSQLAdapter, ValidationError

# Create FastMCP server
mcp = FastMCP("SQLite Lab FastMCP Server")

# Determine which adapter to use
DATABASE_URL = os.environ.get("DATABASE_URL")
db_dir = os.path.dirname(os.path.abspath(__file__))
default_db_path = os.path.join(db_dir, "lab.db")

if DATABASE_URL and (DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")):
    print(f"Connecting to PostgreSQL using DSN: {DATABASE_URL}", file=sys.stderr)
    adapter = PostgreSQLAdapter(DATABASE_URL)
else:
    # Default to SQLite
    # If the database doesn't exist, try initializing it
    if not os.path.exists(default_db_path):
        print(f"Database file not found at {default_db_path}. Initializing...", file=sys.stderr)
        try:
            from init_db import create_database
            create_database(default_db_path)
        except Exception as e:
            print(f"Failed to auto-initialize database: {e}", file=sys.stderr)
    
    print(f"Connecting to SQLite database at {default_db_path}", file=sys.stderr)
    adapter = SQLiteAdapter(default_db_path)


@mcp.tool(name="search")
def search(table: str, filters: list = None, columns: list = None, limit: int = 20, offset: int = 0, order_by: str = None, descending: bool = False):
    """Search records in a database table.
    
    Args:
        table: Name of the table.
        filters: Optional filters. Can be a list of filter dicts e.g. [{"column": "cohort", "operator": "=", "value": "A1"}] or a dictionary mapping columns to exact values e.g. {"cohort": "A1"}.
        columns: Optional list of columns to retrieve.
        limit: Max number of records to return.
        offset: Offset of records.
        order_by: Column to sort by.
        descending: Sort in descending order.
    """
    try:
        results = adapter.search(
            table=table,
            columns=columns,
            filters=filters,
            limit=limit,
            offset=offset,
            order_by=order_by,
            descending=descending
        )
        return json.dumps(results, indent=2)
    except ValidationError as e:
        raise ValueError(f"Validation Error: {e}")
    except Exception as e:
        raise ValueError(f"Database Error: {e}")


@mcp.tool(name="insert")
def insert(table: str, values: dict):
    """Insert a new record into a database table.
    
    Args:
        table: Name of the table.
        values: Dictionary mapping column names to values.
    """
    try:
        inserted = adapter.insert(table=table, values=values)
        return json.dumps(inserted, indent=2)
    except ValidationError as e:
        raise ValueError(f"Validation Error: {e}")
    except Exception as e:
        raise ValueError(f"Database Error: {e}")


@mcp.tool(name="aggregate")
def aggregate(table: str, metric: str, column: str = None, filters: list = None, group_by: str = None):
    """Perform aggregation queries like COUNT, AVG, SUM, MIN, MAX on a table.
    
    Args:
        table: Name of the table.
        metric: Aggregation function (COUNT, AVG, SUM, MIN, MAX).
        column: Column to aggregate (optional for COUNT, required for others).
        filters: Optional filters.
        group_by: Optional column to group by.
    """
    try:
        results = adapter.aggregate(
            table=table,
            metric=metric,
            column=column,
            filters=filters,
            group_by=group_by
        )
        return json.dumps(results, indent=2)
    except ValidationError as e:
        raise ValueError(f"Validation Error: {e}")
    except Exception as e:
        raise ValueError(f"Database Error: {e}")


@mcp.resource("schema://database")
def database_schema() -> str:
    """Get the schema of all tables in the database."""
    try:
        tables = adapter.list_tables()
        schema_snapshot = {}
        for table in tables:
            schema_snapshot[table] = adapter.get_table_schema(table)
        return json.dumps(schema_snapshot, indent=2)
    except Exception as e:
        raise ValueError(f"Failed to fetch database schema: {e}")


@mcp.resource("schema://table/{table_name}")
def table_schema(table_name: str) -> str:
    """Get the schema of a specific table in the database."""
    try:
        schema = adapter.get_table_schema(table_name)
        return json.dumps(schema, indent=2)
    except ValidationError as e:
        raise ValueError(f"Validation Error: {e}")
    except Exception as e:
        raise ValueError(f"Failed to fetch table schema: {e}")


if __name__ == "__main__":
    # fastmcp uses standard run() which handles stdio and optional sse
    mcp.run()
