import sys
import os
import pytest
import json

# Add implementation directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db import SQLiteAdapter, ValidationError
from init_db import create_database
from mcp_server import search, insert, aggregate, database_schema, table_schema

TEST_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_lab.db"))

@pytest.fixture(scope="function")
def test_db():
    # Initialize a clean test database
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    
    create_database(TEST_DB_PATH)
    
    # We will temporarily patch the global adapter in mcp_server to use the test database
    import mcp_server
    old_adapter = mcp_server.adapter
    test_adapter = SQLiteAdapter(TEST_DB_PATH)
    mcp_server.adapter = test_adapter
    
    yield test_adapter
    
    # Restore the original adapter
    mcp_server.adapter = old_adapter
    
    # Cleanup
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass


def test_schema_discovery(test_db):
    tables = test_db.list_tables()
    assert "students" in tables
    assert "courses" in tables
    assert "enrollments" in tables
    
    schema = test_db.get_table_schema("students")
    assert "name" in schema
    assert "cohort" in schema
    assert "email" in schema
    assert schema["id"]["pk"] is True


def test_search_valid(test_db):
    # Test through adapter
    results = test_db.search("students", filters={"cohort": "A1"})
    assert len(results) == 2
    assert results[0]["name"] == "Alice"
    assert results[1]["name"] == "Bob"

    # Test through FastMCP tool
    res_str = search("students", filters=[{"column": "cohort", "operator": "=", "value": "A1"}])
    res_json = json.loads(res_str)
    assert len(res_json) == 2
    assert res_json[0]["name"] == "Alice"


def test_search_invalid(test_db):
    with pytest.raises(ValidationError):
        test_db.search("missing_table")

    with pytest.raises(ValidationError):
        test_db.search("students", columns=["nonexistent_col"])

    with pytest.raises(ValidationError):
        test_db.search("students", filters=[{"column": "name", "operator": "BETWEEN", "value": [1, 2]}])


def test_insert_valid(test_db):
    new_student = {"name": "David", "cohort": "B2", "email": "david@example.com"}
    # Test through FastMCP tool
    inserted_str = insert("students", new_student)
    inserted = json.loads(inserted_str)
    assert inserted["id"] == 4
    assert inserted["name"] == "David"

    # Verify via search
    results = test_db.search("students", filters={"email": "david@example.com"})
    assert len(results) == 1
    assert results[0]["name"] == "David"


def test_insert_invalid(test_db):
    # Empty insert
    with pytest.raises(ValueError, match="Validation Error"):
        insert("students", {})

    # Invalid column
    with pytest.raises(ValueError, match="Validation Error"):
        insert("students", {"name": "Eve", "age": 20})


def test_aggregate_valid(test_db):
    # Test count through FastMCP tool
    count_str = aggregate("students", "count")
    count_res = json.loads(count_str)
    assert count_res[0]["value"] == 3

    # Test avg grade
    avg_str = aggregate("enrollments", "avg", column="grade")
    avg_res = json.loads(avg_str)
    assert avg_res[0]["value"] == 87.7


def test_aggregate_invalid(test_db):
    with pytest.raises(ValueError, match="Validation Error"):
        aggregate("students", "invalid_metric")

    with pytest.raises(ValueError, match="Validation Error"):
        aggregate("students", "avg") # Missing column for AVG


def test_resources(test_db):
    # Test database schema resource
    db_schema_str = database_schema()
    db_schema = json.loads(db_schema_str)
    assert "students" in db_schema
    assert "courses" in db_schema

    # Test table schema resource
    table_schema_str = table_schema("students")
    tbl_schema = json.loads(table_schema_str)
    assert "email" in tbl_schema
