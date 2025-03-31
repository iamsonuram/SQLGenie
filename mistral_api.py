import requests
import json
import sqlite3

MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_API_KEY = "jDcCdZ0dkkTKEjAfVIoLWbRcmZ4ktwBs"
MISTRAL_AGENT_ID = "ag:79ec7e4f:20250328:untitled-agent:36859aa3"

PLOTS_DIR = "static/plots"
PLOT_SCRIPT = "plot.py"
CSV_OUTPUT = "generated_data.csv"  # File where query results will be saved

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

    print(f"🟢 Sending request to Mistral with schema:\n{table_schema}")
    print(f"🟢 User Query: {user_input}")


    if response.status_code == 200:
        result = response.json()["choices"][0]["message"]["content"].strip()

        if "ERROR: No relevant table found" in result:
            return None  # No matching table found
 
        if result.lower().startswith("select"):
            return result  # Return valid SQL query

        return None  # Invalid response
    else:
        return f"Error: {response.status_code}, {response.text}"
    
def call_mistral_for_visualization(CSV_OUTPUT):
    """Uses Mistral Agent to generate a visualization script based on CSV data."""
    
    with open(CSV_OUTPUT, "r") as f:
        csv_data = f.read()

    prompt = f"""
    You are an expert Python developer.
    Given the following CSV data, generate only a valid Python script that:
    - Sets Matplotlib to the non-interactive 'Agg' backend BEFORE ANY IMPORTS using:
    ```python
    import matplotlib
    matplotlib.use('Agg')
    IMPORTANT:
    1. Return ONLY the Python code in plain text.
    2. Do NOT include explanations, comments, or markdown formatting.
    3. Ensure the script is immediately executable and works in a server-side context.
    4. Follow the exact import order: set matplotlib.use('Agg') first, then import other libraries.
    5. Do not insert backslashes (\) before underscores in variable names or file paths. Use pd.read_csv("generated_data.csv"), not pd.read\_csv("generated\_data.csv").
    6. 6. Resolve all the import issues.
        
    CSV Data:
    {csv_data}

    **IMPORTANT:**  
    - **Return only the Python code** in plain text.  
    - **Clears old plots** from the `static/plots` directory.
    - **Make sure to include all necessary imports**
    - **Reads a CSV file** named `"generated_data.csv"` using: df = pd.read_csv("generated_data.csv")  # Ensure correct syntax, no backslashes.
    - **Do not include any explanations, comments, or markdown formatting.**  
    - **Ensure the script is immediately executable.**  
    - **Do not insert backslashes (\) before underscores in variable names or file paths. Use pd.read_csv("generated_data.csv"), not pd.read\_csv("generated\_data.csv").**
    """

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "agent_id": MISTRAL_AGENT_ID,
        "messages": [{"role": "user", "content": prompt}]
    }

    response = requests.post("https://api.mistral.ai/v1/agents/completions", headers=headers, json=payload)
    print("Mistral Response:", response.text)
    if response.status_code == 200:
        generated_code = response.json()["choices"][0]["message"]["content"]
        with open("plot.py", "w") as f:
            f.write(generated_code)
        return generated_code
    else:
        return "print('Error: Failed to generate visualization code')"
