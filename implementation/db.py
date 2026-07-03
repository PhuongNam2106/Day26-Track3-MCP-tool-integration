import sqlite3
import os

try:
    import pg8000
    PG_AVAILABLE = True
except ImportError:
    PG_AVAILABLE = False


class ValidationError(Exception):
    """Raised when database input validation fails."""
    pass


class BaseAdapter:
    def __init__(self):
        self._schema_cache = {}  # {table_name: {column_name: column_metadata}}
        self._tables = []        # [table_names]

    def refresh_schema(self):
        raise NotImplementedError

    def list_tables(self):
        raise NotImplementedError

    def get_table_schema(self, table):
        raise NotImplementedError

    def search(self, table, columns=None, filters=None, limit=20, offset=0, order_by=None, descending=False):
        raise NotImplementedError

    def insert(self, table, values):
        raise NotImplementedError

    def aggregate(self, table, metric, column=None, filters=None, group_by=None):
        raise NotImplementedError

    def validate_table(self, table):
        if not self._tables:
            self.refresh_schema()
        if table not in self._tables:
            raise ValidationError(f"Table '{table}' does not exist. Available tables: {', '.join(self._tables)}")

    def validate_columns(self, table, columns):
        self.validate_table(table)
        schema = self._schema_cache[table]
        for col in columns:
            if col not in schema:
                raise ValidationError(f"Column '{col}' does not exist in table '{table}'. Available columns: {', '.join(schema.keys())}")

    def validate_filters(self, table, filters):
        if not filters:
            return
        if isinstance(filters, dict):
            # Normalize dict to list of dicts
            filters_list = []
            for col, val in filters.items():
                filters_list.append({"column": col, "operator": "=", "value": val})
            filters = filters_list

        if not isinstance(filters, list):
            raise ValidationError("Filters must be a list of filter conditions or a dictionary.")

        allowed_operators = {"=", "!=", ">", ">=", "<", "<=", "LIKE", "IN"}
        for f in filters:
            if not isinstance(f, dict) or "column" not in f or "operator" not in f or "value" not in f:
                raise ValidationError("Each filter must contain 'column', 'operator', and 'value' fields.")
            col = f["column"]
            op = f["operator"].upper()
            val = f["value"]
            self.validate_columns(table, [col])
            if op not in allowed_operators:
                raise ValidationError(f"Unsupported operator '{op}'. Supported operators: {', '.join(allowed_operators)}")
            if op == "IN" and not isinstance(val, (list, tuple)):
                raise ValidationError("For 'IN' operator, 'value' must be a list or tuple.")

    def build_where_clause(self, table, filters, placeholder="?"):
        if not filters:
            return "", []

        if isinstance(filters, dict):
            filters_list = []
            for col, val in filters.items():
                filters_list.append({"column": col, "operator": "=", "value": val})
            filters = filters_list

        sql_parts = []
        params = []
        for f in filters:
            col = f["column"]
            op = f["operator"].upper()
            val = f["value"]
            safe_col = f'"{col}"'

            if op == "IN":
                if not val:
                    # Handle empty IN list safely
                    sql_parts.append("1 = 0")
                else:
                    in_placeholders = ", ".join([placeholder] * len(val))
                    sql_parts.append(f"{safe_col} IN ({in_placeholders})")
                    params.extend(val)
            else:
                sql_parts.append(f"{safe_col} {op} {placeholder}")
                params.append(val)

        return " WHERE " + " AND ".join(sql_parts), params


class SQLiteAdapter(BaseAdapter):
    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path
        self.refresh_schema()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def refresh_schema(self):
        conn = self.connect()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            self._tables = [row["name"] for row in cursor.fetchall()]
            
            self._schema_cache = {}
            for table in self._tables:
                cursor.execute(f"PRAGMA table_info({table});")
                columns = {}
                for row in cursor.fetchall():
                    columns[row["name"]] = {
                        "type": row["type"],
                        "notnull": bool(row["notnull"]),
                        "dflt_value": row["dflt_value"],
                        "pk": bool(row["pk"])
                    }
                self._schema_cache[table] = columns
        finally:
            conn.close()

    def list_tables(self):
        self.refresh_schema()
        return self._tables

    def get_table_schema(self, table):
        self.validate_table(table)
        return self._schema_cache[table]

    def search(self, table, columns=None, filters=None, limit=20, offset=0, order_by=None, descending=False):
        self.validate_table(table)
        if columns:
            self.validate_columns(table, columns)
            select_cols = ", ".join(f'"{col}"' for col in columns)
        else:
            select_cols = "*"

        self.validate_filters(table, filters)
        where_clause, params = self.build_where_clause(table, filters, "?")

        order_clause = ""
        if order_by:
            self.validate_columns(table, [order_by])
            direction = "DESC" if descending else "ASC"
            order_clause = f' ORDER BY "{order_by}" {direction}'

        if not isinstance(limit, int) or limit < 0:
            raise ValidationError("Limit must be a non-negative integer.")
        if not isinstance(offset, int) or offset < 0:
            raise ValidationError("Offset must be a non-negative integer.")

        sql = f'SELECT {select_cols} FROM "{table}"{where_clause}{order_clause} LIMIT {limit} OFFSET {offset};'
        
        conn = self.connect()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def insert(self, table, values):
        self.validate_table(table)
        if not values or not isinstance(values, dict):
            raise ValidationError("Insert values must be a non-empty dictionary.")
        
        self.validate_columns(table, values.keys())
        
        cols = list(values.keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_list = ", ".join(f'"{c}"' for c in cols)
        
        sql = f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders});'
        params = list(values.values())
        
        conn = self.connect()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            last_id = cursor.lastrowid
            
            schema = self._schema_cache[table]
            pk_col = next((c for c, meta in schema.items() if meta["pk"]), None)
            
            if pk_col and last_id:
                cursor.execute(f'SELECT * FROM "{table}" WHERE "{pk_col}" = ?;', (last_id,))
                inserted_row = cursor.fetchone()
                if inserted_row:
                    return dict(inserted_row)
            
            return {**values, "id": last_id} if last_id else values
        except sqlite3.IntegrityError as e:
            raise ValidationError(f"Database integrity violation: {e}")
        finally:
            conn.close()

    def aggregate(self, table, metric, column=None, filters=None, group_by=None):
        self.validate_table(table)
        metric = metric.upper()
        if metric not in {"COUNT", "AVG", "SUM", "MIN", "MAX"}:
            raise ValidationError(f"Unsupported metric '{metric}'. Supported: COUNT, AVG, SUM, MIN, MAX")
        
        if column:
            self.validate_columns(table, [column])
            select_expr = f'{metric}("{column}")'
        else:
            if metric != "COUNT":
                raise ValidationError(f"Metric '{metric}' requires a column name.")
            select_expr = "COUNT(*)"

        self.validate_filters(table, filters)
        where_clause, params = self.build_where_clause(table, filters, "?")

        group_clause = ""
        select_cols = f"{select_expr} AS value"
        if group_by:
            self.validate_columns(table, [group_by])
            group_clause = f' GROUP BY "{group_by}"'
            select_cols = f'"{group_by}", {select_expr} AS value'

        sql = f'SELECT {select_cols} FROM "{table}"{where_clause}{group_clause};'
        
        conn = self.connect()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()


class PostgreSQLAdapter(BaseAdapter):
    def __init__(self, dsn):
        super().__init__()
        if not PG_AVAILABLE:
            raise ValidationError("pg8000 is not installed, PostgreSQLAdapter is unavailable.")
        self.dsn = dsn
        self.conn_kwargs = self._parse_dsn(dsn)
        self.refresh_schema()

    def _parse_dsn(self, dsn):
        kwargs = {}
        if not dsn.startswith(("postgresql://", "postgres://")):
            raise ValueError("Invalid PostgreSQL connection string.")
        
        temp = dsn.split("://", 1)[1]
        
        if "@" in temp:
            auth, temp = temp.split("@", 1)
            if ":" in auth:
                kwargs["user"], kwargs["password"] = auth.split(":", 1)
            else:
                kwargs["user"] = auth
        
        if "/" in temp:
            host_port, kwargs["database"] = temp.split("/", 1)
        else:
            host_port = temp
            kwargs["database"] = "postgres"
            
        if ":" in host_port:
            kwargs["host"], port_str = host_port.split(":", 1)
            kwargs["port"] = int(port_str)
        else:
            kwargs["host"] = host_port
            kwargs["port"] = 5432
            
        return kwargs

    def connect(self):
        return pg8000.dbapi.connect(**self.conn_kwargs)

    def refresh_schema(self):
        conn = self.connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
            )
            self._tables = [row[0] for row in cursor.fetchall()]
            
            self._schema_cache = {}
            for table in self._tables:
                cursor.execute(
                    "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
                    "WHERE table_name = %s AND table_schema='public';",
                    (table,)
                )
                columns = {}
                for row in cursor.fetchall():
                    columns[row[0]] = {
                        "type": row[1],
                        "notnull": row[2] == "NO",
                        "dflt_value": None,
                        "pk": False
                    }
                
                cursor.execute(
                    "SELECT c.column_name FROM information_schema.table_constraints tc "
                    "JOIN information_schema.constraint_column_usage AS ccu USING (constraint_schema, constraint_name) "
                    "JOIN information_schema.columns AS c ON c.table_schema = tc.constraint_schema AND c.table_name = tc.table_name AND c.column_name = ccu.column_name "
                    "WHERE constraint_type = 'PRIMARY KEY' AND tc.table_name = %s;",
                    (table,)
                )
                pks = [r[0] for r in cursor.fetchall()]
                for pk in pks:
                    if pk in columns:
                        columns[pk]["pk"] = True
                        
                self._schema_cache[table] = columns
        finally:
            conn.close()

    def list_tables(self):
        self.refresh_schema()
        return self._tables

    def get_table_schema(self, table):
        self.validate_table(table)
        return self._schema_cache[table]

    def search(self, table, columns=None, filters=None, limit=20, offset=0, order_by=None, descending=False):
        self.validate_table(table)
        if columns:
            self.validate_columns(table, columns)
            select_cols = ", ".join(f'"{col}"' for col in columns)
        else:
            select_cols = "*"

        self.validate_filters(table, filters)
        where_clause, params = self.build_where_clause(table, filters, "%s")

        order_clause = ""
        if order_by:
            self.validate_columns(table, [order_by])
            direction = "DESC" if descending else "ASC"
            order_clause = f' ORDER BY "{order_by}" {direction}'

        if not isinstance(limit, int) or limit < 0:
            raise ValidationError("Limit must be a non-negative integer.")
        if not isinstance(offset, int) or offset < 0:
            raise ValidationError("Offset must be a non-negative integer.")

        sql = f'SELECT {select_cols} FROM "{table}"{where_clause}{order_clause} LIMIT {limit} OFFSET {offset};'
        
        conn = self.connect()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            colnames = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(colnames, row)) for row in rows]
        finally:
            conn.close()

    def insert(self, table, values):
        self.validate_table(table)
        if not values or not isinstance(values, dict):
            raise ValidationError("Insert values must be a non-empty dictionary.")
        
        self.validate_columns(table, values.keys())
        
        cols = list(values.keys())
        placeholders = ", ".join(["%s"] * len(cols))
        col_list = ", ".join(f'"{c}"' for c in cols)
        
        sql = f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) RETURNING *;'
        params = list(values.values())
        
        conn = self.connect()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            inserted_row = cursor.fetchone()
            conn.commit()
            if inserted_row:
                colnames = [desc[0] for desc in cursor.description]
                return dict(zip(colnames, inserted_row))
            return values
        except Exception as e:
            conn.rollback()
            raise ValidationError(f"PostgreSQL insert failed: {e}")
        finally:
            conn.close()

    def aggregate(self, table, metric, column=None, filters=None, group_by=None):
        self.validate_table(table)
        metric = metric.upper()
        if metric not in {"COUNT", "AVG", "SUM", "MIN", "MAX"}:
            raise ValidationError(f"Unsupported metric '{metric}'. Supported: COUNT, AVG, SUM, MIN, MAX")
        
        if column:
            self.validate_columns(table, [column])
            select_expr = f'{metric}("{column}")'
        else:
            if metric != "COUNT":
                raise ValidationError(f"Metric '{metric}' requires a column name.")
            select_expr = "COUNT(*)"

        self.validate_filters(table, filters)
        where_clause, params = self.build_where_clause(table, filters, "%s")

        group_clause = ""
        select_cols = f"{select_expr} AS value"
        if group_by:
            self.validate_columns(table, [group_by])
            group_clause = f' GROUP BY "{group_by}"'
            select_cols = f'"{group_by}", {select_expr} AS value'

        sql = f'SELECT {select_cols} FROM "{table}"{where_clause}{group_clause};'
        
        conn = self.connect()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            colnames = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                mapped_row = {}
                for colname, val in zip(colnames, row):
                    if hasattr(val, "to_eng_string") or str(type(val)) == "<class 'decimal.Decimal'>":
                        val = float(val)
                    mapped_row[colname] = val
                result.append(mapped_row)
            return result
        finally:
            conn.close()
