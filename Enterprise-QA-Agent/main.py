import sys
import os
from agent import setup_rag_agent

def run_agent():
    url = 'https://cf-courses-data.s3.us.cloud-object-storage.appdomain.cloud/6JDbUb_L3egv_eOkouY71A.txt'
    filename = 'companyPolicies.txt'
    
    # Automatically get API key from environment if present
    api_key = os.getenv("WATSONX_API_KEY", None)
    
    print("Initializing RAG Agent...")
    try:
        qa_chain = setup_rag_agent(url, filename, api_key)
    except Exception as e:
        print(f"Error initializing agent: {e}")
        sys.exit(1)
        
    print("\n" + "="*50)
    print("Agent is ready! Ask questions about the document.")
    print("Type 'quit', 'exit', or 'bye' to stop.")
    print("="*50 + "\n")
    
    history = []
    while True:
        try:
            query = input("Question: ")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break
            
        if query.lower() in ["quit", "exit", "bye"]:
            print("Answer: Goodbye!")
            break
            
        result = qa_chain.invoke({"question": query, "chat_history": history})
        answer = result.get("answer", "No answer found.")
        
        history.append((query, answer))
        print(f"\nAnswer: {answer}")
        print("-" * 50)

if __name__ == "__main__":
    run_agent()
