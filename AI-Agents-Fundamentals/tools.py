import os
import glob
from typing import List, Optional, Dict, Any, Union
import re
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, r2_score, mean_squared_error
from langchain_core.tools import tool

# --- Math Tools ---

@tool
def add_numbers(inputs: str) -> dict:
    """Adds a list of numbers provided in the input string."""
    numbers = [int(num) for num in re.findall(r'\d+', inputs)]
    return {"result": sum(numbers)}

@tool
def subtract_numbers(inputs: str) -> dict:
    """Extracts numbers from a string and performs subtraction sequentially, starting with the first number."""
    numbers = [int(num) for num in inputs.replace(",", "").split() if num.isdigit()]
    if not numbers:
        return {"result": 0}
    result = numbers[0]
    for num in numbers[1:]:
        result -= num
    return {"result": result}

@tool
def multiply_numbers(inputs: str) -> dict:
    """Extracts numbers from a string and calculates their product."""
    numbers = [int(num) for num in inputs.replace(",", "").split() if num.isdigit()]
    if not numbers:
        return {"result": 1}
    result = 1
    for num in numbers:
        result *= num
    return {"result": result}

@tool
def divide_numbers(inputs: str) -> dict:
    """Extracts numbers from a string and calculates the result of dividing the first number by the subsequent numbers."""
    numbers = [int(num) for num in inputs.replace(",", "").split() if num.isdigit()]
    if not numbers:
        return {"result": 0}
    result = numbers[0]
    for num in numbers[1:]:
        if num == 0:
            return {"error": "Division by zero is not allowed."}
        result /= num
    return {"result": result}


# --- Data Science Tools ---

DATAFRAME_CACHE = {}

@tool
def list_csv_files() -> Optional[List[str]]:
    """List all CSV file names in the local directory."""
    csv_files = glob.glob(os.path.join(os.getcwd(), "*.csv"))
    if not csv_files:
        return None
    return [os.path.basename(file) for file in csv_files]

@tool
def preload_datasets(paths: List[str]) -> str:
    """Loads CSV files into a global cache if not already loaded."""
    loaded = []
    cached = []
    for path in paths:
        if path not in DATAFRAME_CACHE:
            DATAFRAME_CACHE[path] = pd.read_csv(path)
            loaded.append(path)
        else:
            cached.append(path)
    return f"Loaded datasets: {loaded}\nAlready cached: {cached}"

@tool
def get_dataset_summaries(dataset_paths: List[str]) -> List[Dict[str, Any]]:
    """Analyze multiple CSV files and return metadata summaries for each."""
    summaries = []
    for path in dataset_paths:
        if path not in DATAFRAME_CACHE:
            DATAFRAME_CACHE[path] = pd.read_csv(path)
        df = DATAFRAME_CACHE[path]
        summary = {
            "file_name": path,
            "column_names": df.columns.tolist(),
            "data_types": df.dtypes.astype(str).to_dict()
        }
        summaries.append(summary)
    return summaries

@tool
def call_dataframe_method(file_name: str, method: str) -> str:
   """Execute a no-argument method on a DataFrame and return the result."""
   if file_name not in DATAFRAME_CACHE:
       try:
           DATAFRAME_CACHE[file_name] = pd.read_csv(file_name)
       except Exception as e:
           return f"Error loading '{file_name}': {str(e)}"
   df = DATAFRAME_CACHE[file_name]
   func = getattr(df, method, None)
   if not callable(func):
       return f"'{method}' is not a valid method of DataFrame."
   try:
       return str(func())
   except Exception as e:
       return f"Error calling '{method}': {str(e)}"

@tool
def evaluate_classification_dataset(file_name: str, target_column: str) -> Dict[str, Union[float, str]]:
    """Train and evaluate a classifier on a dataset using the specified target column."""
    if file_name not in DATAFRAME_CACHE:
        try:
            DATAFRAME_CACHE[file_name] = pd.read_csv(file_name)
        except Exception as e:
            return {"error": f"Error loading '{file_name}': {str(e)}"}
    df = DATAFRAME_CACHE[file_name]
    if target_column not in df.columns:
        return {"error": f"Target column '{target_column}' not found."}
    
    X = df.drop(columns=[target_column])
    y = df[target_column]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestClassifier()
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    return {"accuracy": accuracy_score(y_test, y_pred)}

@tool
def evaluate_regression_dataset(file_name: str, target_column: str) -> Dict[str, Union[float, str]]:
    """Train and evaluate a regression model on a dataset using the specified target column."""
    if file_name not in DATAFRAME_CACHE:
        try:
            DATAFRAME_CACHE[file_name] = pd.read_csv(file_name)
        except Exception as e:
            return {"error": f"Error loading '{file_name}': {str(e)}"}
    df = DATAFRAME_CACHE[file_name]
    if target_column not in df.columns:
        return {"error": f"Target column '{target_column}' not found."}
    
    X = df.drop(columns=[target_column])
    y = df[target_column]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestRegressor()
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    return {
        "r2_score": r2_score(y_test, y_pred),
        "mean_squared_error": mean_squared_error(y_test, y_pred)
    }
