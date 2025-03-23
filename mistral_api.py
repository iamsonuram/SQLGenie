import requests
import json
import sqlite3

MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

def load_database_schema(db_path):
    """Loads the schema of the uploaded SQLite database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    schema = ""

    for table in tables:
        table_name = table[0]
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        schema += f"Table: {table_name}\n"
        schema += ", ".join([f"{col[1].lower()} ({col[2]})" for col in columns]) + "\n\n"  # Ensure lowercase column names

    conn.close()
    return schema.strip()

def generate_sql(user_input, api_key, db_path):
    """Converts a natural language query to SQL using Mistral API."""
    table_schema = load_database_schema(db_path)  # Get the latest schema

    prompt = (
        f"Based on the following database schema, generate only a complete and executable SQL query without any explanation. "
        f"Ensure the query includes the FROM clause and necessary conditions. "
        f"If the request is unrelated to the schema, return 'ERROR: No relevant table found'.\n"
        f"Schema:\n{table_schema}\n"
        f"User request: '{user_input}'"
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "mistral-medium",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }

    response = requests.post(MISTRAL_URL, headers=headers, data=json.dumps(payload))

    if response.status_code == 200:
        result = response.json()["choices"][0]["message"]["content"].strip()

        if "ERROR: No relevant table found" in result:
            return None  # No matching table found

        if result.lower().startswith("select"):
            return result  # Return valid SQL query

        return None  # Invalid response
    else:
        return f"Error: {response.status_code}, {response.text}"