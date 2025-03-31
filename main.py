from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from mistral_api import generate_sql, call_mistral_for_visualization
from pydantic import BaseModel
import sqlite3
import pandas as pd
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import sys
import json
import subprocess
import logging  # Added for debugging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Serve static files (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

UPLOAD_FOLDER = "db/"
DB_PATH = "db/database.db"
CSV_OUTPUT = "generated_data.csv"
PLOT_SCRIPT = "plot.py"
PLOTS_DIR = "static/plots"
MISTRAL_API_KEY = None

# Ensure PLOTS_DIR exists
os.makedirs(PLOTS_DIR, exist_ok=True)

class SQLRequest(BaseModel):
    sql_query: str

class QueryRequest(BaseModel):
    user_query: str

@app.get("/")
def read_root():
    return FileResponse(os.path.join("templates", "index.html"))

@app.post("/set_api_key")
def set_api_key(api_key: str = Form(...)):
    global MISTRAL_API_KEY
    MISTRAL_API_KEY = api_key
    return {"message": "API Key set successfully!"}

@app.post("/upload_db")
def upload_database(file: UploadFile = File(...)):
    global DB_PATH
    db_filename = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(db_filename, "wb") as buffer:
        buffer.write(file.file.read())
    DB_PATH = db_filename
    return {"message": f"Database '{file.filename}' uploaded successfully!"}

@app.get("/get_tables")
def get_tables():
    if not DB_PATH:
        raise HTTPException(status_code=400, detail="No database uploaded.")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [table[0] for table in cursor.fetchall()]
    conn.close()
    return {"tables": tables}

@app.post("/execute_sql")
def execute_sql_endpoint(request: SQLRequest):
    result = execute_sql(request.sql_query)
    logger.info("SQL Execution Result: %s", result)
    return result

def execute_sql(sql_query):
    if not sql_query or not DB_PATH:
        return {"error": "No valid SQL query or database selected."}
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(sql_query)
        result = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description]
        if not result:
            return {"message": "Query executed successfully, but no results found.", "columns": column_names, "data": []}
        data = [dict(zip(column_names, row)) for row in result]
        df = pd.DataFrame(result, columns=column_names)
        df.to_csv(CSV_OUTPUT, index=False)
        return {"success": True, "columns": column_names, "rows": result}
    except sqlite3.Error as e:
        return {"error": f"SQL Error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected Error: {str(e)}"}
    finally:
        conn.close()

@app.post("/generate_visualizations")
def generate_visualizations():
    if not os.path.exists(CSV_OUTPUT):
        logger.error("No query results found at %s", CSV_OUTPUT)
        raise HTTPException(status_code=400, detail="No query results found. Execute a query first!")
    try:
        logger.info("Generating plot script for %s", CSV_OUTPUT)
        generate_plot_script(CSV_OUTPUT)
        logger.info("Executing plot script")
        execute_plot_script()
        plots = list_available_plots()
        if not plots:
            logger.warning("No plots generated in %s", PLOTS_DIR)
            return {"message": "Visualizations attempted but no plots found."}
        return {"message": "Visualizations generated successfully!", "plots": plots}
    except Exception as e:
        logger.error("Error in generate_visualizations: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Error generating visualizations: {str(e)}")

def list_available_plots():
    try:
        return [f for f in os.listdir(PLOTS_DIR) if f.endswith(".png")]
    except Exception as e:
        logger.error("Error listing plots in %s: %s", PLOTS_DIR, str(e))
        return []
    
def generate_plot_script(csv_file):
    # Clear old plots
    for filename in os.listdir(PLOTS_DIR):
        file_path = os.path.join(PLOTS_DIR, filename)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception as e:
            logger.error("Error deleting file %s: %s", file_path, str(e))

    # Generate visualization code via Mistral
    try:
        ai_generated_code = call_mistral_for_visualization(csv_file)
        if not ai_generated_code or "Error" in ai_generated_code:
            logger.error("Mistral returned invalid code: %s", ai_generated_code)
            raise ValueError("Mistral API returned invalid or no code")
        with open(PLOT_SCRIPT, "w") as f:
            f.write(ai_generated_code)
        logger.info("AI-generated plot.py saved successfully")
    except Exception as e:
        logger.error("Error generating plot script: %s", str(e))
        raise

def execute_plot_script():
    venv_python = sys.executable
    try:
        result = subprocess.run(
            [venv_python, PLOT_SCRIPT],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True  # Decode bytes to string
        )
        logger.info("Plot script output: %s", result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error("Error executing plot.py - Exit code: %d, Stderr: %s", e.returncode, e.stderr)
        raise Exception(f"Plot script failed: {e.stderr}")
    except Exception as e:
        logger.error("Unexpected error executing plot.py: %s", str(e))
        raise

@app.get("/latest_plot")
def latest_plot():
    available_plots = list_available_plots()
    if not available_plots:
        raise HTTPException(status_code=404, detail="No plots available.")
    latest_plot = sorted(available_plots, reverse=True)[0]
    return {"filename": latest_plot}

@app.get("/list_plots")
def list_plots():
    available_plots = list_available_plots()
    if not available_plots:
        return {"plots": [], "message": "No plots available."}
    return {"plots": sorted(available_plots)}  # Sorted for consistent ordering

@app.post("/generate_sql")
def generate_sql_endpoint(request: QueryRequest):
    if not MISTRAL_API_KEY:
        return {"error": "Mistral API key not set. Please enter your API key first."}
    sql_query = generate_sql(request.user_query, MISTRAL_API_KEY, DB_PATH)
    if sql_query:
        return {"sql_query": sql_query}
    return {"error": "No relevant table found."}