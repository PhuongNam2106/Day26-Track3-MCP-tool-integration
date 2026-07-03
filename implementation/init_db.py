import sqlite3
import os

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cohort TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    credits INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    grade REAL,
    FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
);
"""

SEED_SQL = """
-- Seed students
INSERT OR IGNORE INTO students (id, name, cohort, email) VALUES
(1, 'Alice', 'A1', 'alice@example.com'),
(2, 'Bob', 'A1', 'bob@example.com'),
(3, 'Charlie', 'B2', 'charlie@example.com');

-- Seed courses
INSERT OR IGNORE INTO courses (id, title, credits) VALUES
(1, 'CS101', 4),
(2, 'CS102', 4),
(3, 'CS201', 3);

-- Seed enrollments
INSERT OR IGNORE INTO enrollments (id, student_id, course_id, grade) VALUES
(1, 1, 1, 95.0),
(2, 1, 2, 88.0),
(3, 2, 1, 78.5),
(4, 3, 2, 92.0),
(5, 3, 3, 85.0);
"""


def create_database(db_path="lab.db"):
    """
    Creates and seeds the SQLite database.
    """
    # Ensure directory exists
    dir_name = os.path.dirname(db_path)
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(SCHEMA_SQL)
        conn.executescript(SEED_SQL)
        conn.commit()
    finally:
        conn.close()
    return os.path.abspath(db_path)


if __name__ == "__main__":
    db_file = os.path.join(os.path.dirname(__file__), "lab.db")
    print(f"Initializing database at {db_file}...")
    abs_path = create_database(db_file)
    print(f"Database successfully initialized at: {abs_path}")
