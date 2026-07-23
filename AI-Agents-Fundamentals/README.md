# AI Agents Fundamentals

This repository contains foundational projects exploring the core mechanics of Agentic AI, Tool Calling, and LangChain frameworks. The project encapsulates distinct autonomous agent implementations, including mathematical problem-solving assistants and robust data science agents.

## Project Structure
- **`main.py`**: The entry point for running the agents. It orchestrates the initialization and execution of both the mathematical and data science agents.
- **`tools.py`**: Contains all custom tools using the LangChain `@tool` decorator, divided into numerical operations and data analysis routines (e.g., caching, model evaluation, dataset summaries).
- **`requirements.txt`**: Project dependencies.

## Technologies Used
- LangChain / LangGraph
- OpenAI API
- Pandas & Scikit-Learn
- Python 3

## Usage
Install the requirements and set your `OPENAI_API_KEY` before running the `main.py` script:
```bash
pip install -r requirements.txt
export OPENAI_API_KEY="your_api_key_here"
python main.py
```
