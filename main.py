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


def execute_sql(sql_query):
    """Executes the given SQL query, detects data types, and returns structured results."""
    if not sql_query or not DB_PATH:
        return {"error": "No valid SQL query or database selected."}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        df = pd.read_sql_query(sql_query, conn)
        conn.close()

        # Detect column types
        column_types = {}
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                column_types[col] = "numeric"
            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                column_types[col] = "datetime"
            else:
                column_types[col] = "categorical"

        result = {
            "columns": df.columns.tolist(),
            "data": df.values.tolist(),
            "column_types": column_types  # Send data types to frontend
        }

        # Check if the data is suitable for visualization
        if is_valid_for_visualization(df):
            result["chart_data"] = generate_chart_data(df)  # Convert data for Chart.js

        return result
    except Exception as e:
        conn.close()
        return {"error": str(e)}


def generate_chart_data(df):
    """
    Converts DataFrame into Chart.js compatible format.
    """
    chart_data = {
        "labels": df[df.columns[0]].tolist(),  # Use first column as labels (categories)
        "datasets": []
    }

    for col in df.columns[1:]:  # Skip first column (assuming categorical)
        if pd.api.types.is_numeric_dtype(df[col]):
            dataset = {
                "label": col,
                "data": df[col].tolist(),
                "backgroundColor": "rgba(54, 162, 235, 0.5)"
            }
            chart_data["datasets"].append(dataset)

    return chart_data


@app.post("/generate_sql")
def generate_sql_endpoint(user_query: str):
    """API endpoint to convert NL query to SQL using user-provided API key."""
    if not MISTRAL_API_KEY:
        return {"error": "Mistral API key not set. Please enter your API key first."}

    sql_query = generate_sql(user_query, MISTRAL_API_KEY, DB_PATH)
    if sql_query:
        return {"sql_query": sql_query}
    return {"error": "No relevant table found."}


@app.post("/execute_sql")
def execute_sql_endpoint(request: SQLRequest):
    """API endpoint to execute SQL queries and return results."""
    return execute_sql(request.sql_query)
