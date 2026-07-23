import os
from langchain_openai import ChatOpenAI
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from tools import (
    add_numbers, subtract_numbers, multiply_numbers, divide_numbers,
    list_csv_files, preload_datasets, get_dataset_summaries,
    call_dataframe_method, evaluate_classification_dataset,
    evaluate_regression_dataset
)

def run_math_assistant():
    print("--- Math Assistant ---")
    llm = init_chat_model("gpt-4o-mini", model_provider="openai", streaming=False)
    math_tools = [add_numbers, subtract_numbers, multiply_numbers, divide_numbers]
    math_agent = create_react_agent(
        model=llm,
        tools=math_tools,
        prompt="You are a helpful mathematical assistant. Use the provided tools precisely."
    )
    
    query = "Subtract 100, 20, and 10."
    print(f"Query: {query}")
    response = math_agent.invoke({"messages": [("human", query)]})
    print(f"Agent Response: {response['messages'][-1].content}\n")

def run_data_science_assistant():
    print("--- Data Science Assistant ---")
    llm = init_chat_model("gpt-4o-mini", model_provider="openai", streaming=False)
    ds_tools = [
        list_csv_files, preload_datasets, get_dataset_summaries, 
        call_dataframe_method, evaluate_classification_dataset, 
        evaluate_regression_dataset
    ]
    ds_agent = create_react_agent(
        model=llm,
        tools=ds_tools,
        prompt="You are a data science assistant. Use the tools to analyze CSV datasets."
    )
    
    query = "What datasets are available in the current directory?"
    print(f"Query: {query}")
    response = ds_agent.invoke({"messages": [("human", query)]})
    print(f"Agent Response: {response['messages'][-1].content}\n")

if __name__ == '__main__':
    # Ensure OPENAI_API_KEY is set in your environment
    if not os.environ.get("OPENAI_API_KEY"):
        print("Please set the OPENAI_API_KEY environment variable before running.")
    else:
        run_math_assistant()
        run_data_science_assistant()
