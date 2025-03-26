from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from mistral_api import generate_sql
from pydantic import BaseModel
import sqlite3
import pandas as pd
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

app = FastAPI()

# Serve static files (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

UPLOAD_FOLDER = "db/"
DB_PATH = "db/database.db"
MISTRAL_API_KEY = None

class SQLRequest(BaseModel):
    sql_query: str  # Expecting JSON with a key `sql_query`

class QueryRequest(BaseModel):
    user_query: str


@app.get("/")
def read_root():
    """Serve the main frontend page."""
    return FileResponse(os.path.join("templates", "index.html"))


@app.post("/set_api_key")
def set_api_key(api_key: str = Form(...)):
    """Stores the user-provided Mistral API key."""
    global MISTRAL_API_KEY
    MISTRAL_API_KEY = api_key
    return {"message": "API Key set successfully!"}


@app.post("/upload_db")
def upload_database(file: UploadFile = File(...)):
    """Handles SQLite database uploads."""
    global DB_PATH
    db_filename = os.path.join(UPLOAD_FOLDER, file.filename)

    # Save uploaded file
    with open(db_filename, "wb") as buffer:
        buffer.write(file.file.read())

    DB_PATH = db_filename  # Set new database path
    return {"message": f"Database '{file.filename}' uploaded successfully!"}


@app.get("/get_tables")
def get_tables():
    """Fetches table names from the uploaded database."""
    if not DB_PATH:
        raise HTTPException(status_code=400, detail="No database uploaded.")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [table[0] for table in cursor.fetchall()]
    conn.close()

    return {"tables": tables}


def is_valid_for_visualization(df):
    """
    Checks if the SQL query result is suitable for visualization.
    """
    if df.empty:
        return False  # No data to plot

    num_cols = df.select_dtypes(include=['number']).columns
    cat_cols = df.select_dtypes(include=['object']).columns

    # Conditions for plotting
    if len(num_cols) == 0:  
        return False  # No numeric data, so skip visualization
    if len(cat_cols) == 0 and 'date' not in df.columns:
        return False  # No categorical or time-series data, so skip visualization

    return True  # Valid for visualization


@app.post("/execute_sql")
def execute_sql_endpoint(request: SQLRequest):
    """Executes an SQL query and returns the results."""
    return execute_sql(request.sql_query)


def execute_sql(sql_query):
    """Executes the given SQL query, detects data types, and returns structured results."""
    if not sql_query or not DB_PATH:
        return {"error": "No valid SQL query or database selected."}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute(sql_query)
        result = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description]

        if not result:
            return {"message": "Query executed successfully, but no results found.", "data": []}

        result_list = [dict(zip(column_names, row)) for row in result]
        df = pd.DataFrame(result_list)

        response = {"data": result_list, "columns": column_names}

        # Check if the data is suitable for visualization
        if is_valid_for_visualization(df):
            response["chart_data"] = generate_chart_data(df)  # Convert data for Chart.js

        return response

    except sqlite3.Error as e:
        return {"error": f"SQL Error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected Error: {str(e)}"}
    finally:
        conn.close()


def generate_chart_data(df):
    """
    Converts DataFrame into Chart.js compatible format dynamically.
    """
    column_types = {}

    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            column_types[col] = "numeric"
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            column_types[col] = "datetime"
        else:
            column_types[col] = "categorical"

    # Default selection of columns for visualization
    first_column = df.columns[0]  # X-axis
    second_column = df.columns[1] if len(df.columns) > 1 else None  # Y-axis

    chart_type = "bar"  # Default chart
    labels = df[first_column].astype(str).tolist()
    values = df[second_column].tolist() if second_column else []

    if column_types[first_column] == "categorical" and column_types[second_column] == "numeric":
        chart_type = "bar"
    elif column_types[first_column] == "numeric" and column_types[second_column] == "numeric":
        chart_type = "scatter"
    elif column_types[first_column] == "datetime" and column_types[second_column] == "numeric":
        chart_type = "line"
    elif column_types[second_column] == "categorical":
        chart_type = "pie"
        labels = df[second_column].astype(str).tolist()
        values = df[first_column].tolist()

    return {
        "chart_type": chart_type,
        "labels": labels,
        "datasets": [{
            "label": second_column if second_column else first_column,
            "data": values,
            "backgroundColor": "rgba(54, 162, 235, 0.5)"
        }],
        "column_types": column_types
    }


@app.post("/generate_sql")
def generate_sql_endpoint(request: QueryRequest):
    """API endpoint to convert NL query to SQL using user-provided API key."""
    if not MISTRAL_API_KEY:
        return {"error": "Mistral API key not set. Please enter your API key first."}

    sql_query = generate_sql(request.user_query, MISTRAL_API_KEY, DB_PATH)

    if sql_query:
        print(f"Generated SQL Query: {sql_query}")  # Debugging
        return {"sql_query": sql_query}
    return {"error": "No relevant table found."}
