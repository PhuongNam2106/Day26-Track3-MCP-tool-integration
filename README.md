# Database MCP Server with FastMCP and SQLite

This project is a Model Context Protocol (MCP) server that exposes a relational database (SQLite by default, with PostgreSQL support behind a shared interface) to LLMs via standard tools and schema resources.

It has been built using **Python**, **FastMCP**, and **SQLite**.

---

## 📂 Project Structure

```text
implementation/
  db.py                # Database connection adapters and SQL query validation
  init_db.py           # Database creation and seeding script
  mcp_server.py        # FastMCP server exposing tools and resources
  verify_server.py     # Smoke-test script verifying valid & invalid inputs
  tests/
    test_server.py     # Automated unit tests using pytest
  lab.db               # SQLite database file (generated)
```

---

## 🛠️ Setup Instructions

### 1. Initialize Virtual Environment & Install Dependencies

Ensure Python 3.10+ is installed. Create a virtual environment and install the required packages:

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install fastmcp pytest pg8000
```

### 2. Initialize and Seed the Database

Run the database initialization script to create the `students`, `courses`, and `enrollments` tables, and seed them with sample data:

```bash
python implementation/init_db.py
```

---

## 🚀 Running the Server

Start the FastMCP server in standard I/O (stdio) mode (which is default and recommended for most MCP clients):

```bash
python implementation/mcp_server.py
```

To run with **PostgreSQL** support (Bonus Feature), set the `DATABASE_URL` environment variable:

```bash
$env:DATABASE_URL="postgresql://username:password@localhost:5432/dbname"
python implementation/mcp_server.py
```

---

## 🔍 Exponent Tools & Resources

### 1. Tools

The server exposes three powerful, parameterized, and fully validated tools to the LLM:

*   **`search`**: Retrieves records from a database table.
    *   `table` (string, required): Table name to query.
    *   `filters` (list or dict, optional): List of filter rules (e.g. `[{"column": "cohort", "operator": "=", "value": "A1"}]`) or shorthand dict (e.g. `{"cohort": "A1"}`). Supported operators: `=`, `!=`, `>`, `>=`, `<`, `<=`, `LIKE`, `IN`.
    *   `columns` (list, optional): Columns to select.
    *   `limit` (int, default 20): Max rows to return.
    *   `offset` (int, default 0): Rows to skip.
    *   `order_by` (string, optional): Column to sort by.
    *   `descending` (bool, default False): Sort descending.
*   **`insert`**: Inserts a new record.
    *   `table` (string, required): Table name.
    *   `values` (dict, required): Dictionary of column-value pairs.
*   **`aggregate`**: Computes metrics on tables.
    *   `table` (string, required): Table name.
    *   `metric` (string, required): Aggregation metric (`COUNT`, `AVG`, `SUM`, `MIN`, `MAX`).
    *   `column` (string, optional): Column to aggregate (required for all except `COUNT`).
    *   `filters` (list, optional): Filters to apply.
    *   `group_by` (string, optional): Column to group results by.

### 2. Resources

Dynamic schema context is exposed to the LLM via standard MCP resource URIs:

*   **`schema://database`**: Returns the full database schema as JSON.
*   **`schema://table/{table_name}`**: Returns schema metadata (columns, types, nullability, primary keys) for the specified table.

---

## 🛡️ Input Validation & Safety

To prevent SQL injection, all SQL queries are strictly validated:
1.  **Identifier Validation**: Table and column names are cross-referenced with the database metadata before execution. Unknown tables/columns are rejected immediately.
2.  **Operator Validation**: Only safe operators (`=`, `!=`, `>`, `>=`, `<`, `<=`, `LIKE`, `IN`) are accepted.
3.  **Parameterized SQL**: All query values are passed as parameters (`?` for SQLite, `%s` for PostgreSQL), avoiding raw string concatenation.
4.  **Constraints**: Empty inserts and invalid metrics are rejected with clear validation error messages.

---

## 🧪 Verification & Testing

### 1. Interactive Tests (Smoke Test)

Run the verification script to test queries, inserts, aggregates, and rejection of bad input:

```bash
python implementation/verify_server.py
```

### 2. Automated Unit Tests

Run the full automated test suite using `pytest`:

```bash
pytest implementation/tests/
```

### 3. MCP Inspector

Use the MCP Inspector to test the server dynamically in a visual UI:

```bash
npx @modelcontextprotocol/inspector python implementation/mcp_server.py
```

---

## 💻 Client Configurations

Ensure you replace `/ABSOLUTE/PATH` with the real path to your workspace directory.

### 1. Claude Code (`.mcp.json`)

```json
{
  "mcpServers": {
    "sqlite-lab": {
      "type": "stdio",
      "command": "python",
      "args": ["/ABSOLUTE/PATH/TO/implementation/mcp_server.py"]
    }
  }
}
```

### 2. Gemini CLI

Add the server:

```bash
gemini mcp add sqlite-lab /ABSOLUTE/PATH/TO/python /ABSOLUTE/PATH/TO/implementation/mcp_server.py --description "SQLite lab FastMCP server" --timeout 10000
```

Verify the setup:

```bash
gemini mcp list
gemini --allowed-mcp-server-names sqlite-lab --yolo -p "Use the sqlite-lab MCP server to list all students in cohort A1."
```

### 3. Antigravity (`mcp_config.json`)

```json
{
  "mcpServers": {
    "sqlite-lab": {
      "command": "python",
      "args": ["/ABSOLUTE/PATH/TO/implementation/mcp_server.py"],
      "cwd": "/ABSOLUTE/PATH/TO/implementation"
    }
  }
}
```