import os
import json
from db import SQLiteAdapter, ValidationError

def run_verification():
    db_file = os.path.join(os.path.dirname(__file__), "lab.db")
    print("=" * 60)
    print("DATABASE VERIFICATION RUN")
    print("=" * 60)
    print(f"Connecting to SQLite database: {db_file}\n")
    
    adapter = SQLiteAdapter(db_file)
    
    # 1. Database Schema
    print("--- 1. List Tables ---")
    tables = adapter.list_tables()
    print(f"Tables found: {tables}\n")
    
    for table in tables:
        print(f"Schema for '{table}':")
        print(json.dumps(adapter.get_table_schema(table), indent=2))
        print()

    # 2. Search Tools
    print("--- 2. Search: Students in Cohort A1 ---")
    results = adapter.search("students", filters=[{"column": "cohort", "operator": "=", "value": "A1"}])
    print(json.dumps(results, indent=2))
    print()

    print("--- 2b. Search with Dictionary Filter (Shorthand) ---")
    results_shorthand = adapter.search("students", filters={"cohort": "A1"})
    print(json.dumps(results_shorthand, indent=2))
    print()

    # 3. Insert Tool
    print("--- 3. Insert: New Student (David) ---")
    new_student = {"name": "David", "cohort": "B2", "email": "david@example.com"}
    try:
        inserted = adapter.insert("students", new_student)
        print("Success! Inserted row:")
        print(json.dumps(inserted, indent=2))
    except ValidationError as e:
        print(f"Failed to insert: {e}")
    print()

    print("--- 3b. Verify Inserted Student by Search ---")
    search_inserted = adapter.search("students", filters={"email": "david@example.com"})
    print(json.dumps(search_inserted, indent=2))
    print()

    # 4. Aggregate Tool
    print("--- 4. Aggregate: Count all students ---")
    count_students = adapter.aggregate("students", "count")
    print(json.dumps(count_students, indent=2))
    print()

    print("--- 4b. Aggregate: Average Grade ---")
    avg_grade = adapter.aggregate("enrollments", "avg", column="grade")
    print(json.dumps(avg_grade, indent=2))
    print()

    print("--- 4c. Aggregate: Average Grade by Course ---")
    avg_grade_by_course = adapter.aggregate("enrollments", "avg", column="grade", group_by="course_id")
    print(json.dumps(avg_grade_by_course, indent=2))
    print()

    # 5. Validation and Safety Rejections
    print("--- 5. Validation Rejection Tests ---")
    
    # 5a. Bad table
    print("Test 5a: Unknown Table")
    try:
        adapter.search("teachers")
        print("FAIL: Allowed search on unknown table")
    except ValidationError as e:
        print(f"PASS: Rejected as expected: {e}")
    print()

    # 5b. Bad column
    print("Test 5b: Unknown Column")
    try:
        adapter.search("students", columns=["age"])
        print("FAIL: Allowed search with unknown column")
    except ValidationError as e:
        print(f"PASS: Rejected as expected: {e}")
    print()

    # 5c. Bad operator
    print("Test 5c: Unsupported operator")
    try:
        adapter.search("students", filters=[{"column": "name", "operator": "BETWEEN", "value": ["A", "D"]}])
        print("FAIL: Allowed search with unsupported operator")
    except ValidationError as e:
        print(f"PASS: Rejected as expected: {e}")
    print()

    # 5d. Empty Insert
    print("Test 5d: Empty Insert")
    try:
        adapter.insert("students", {})
        print("FAIL: Allowed empty insert")
    except ValidationError as e:
        print(f"PASS: Rejected as expected: {e}")
    print()

    # 5e. Clean up David for repeatable verification run
    print("--- 6. Cleanup Verification Data ---")
    conn = adapter.connect()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM students WHERE email = ?;", ("david@example.com",))
        conn.commit()
        print("Successfully cleaned up David from students.")
    finally:
        conn.close()
    print("=" * 60)

if __name__ == "__main__":
    run_verification()
