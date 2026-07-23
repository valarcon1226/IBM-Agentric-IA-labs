from tools import FaissSemanticSearch, LangchainWatsonxRetriever, LlamaIndexAdvancedRetrievers
from langchain_core.documents import Document as LC_Document
from langchain_community.vectorstores import Chroma

SAMPLE_DOCUMENTS = [
    "Machine learning is a subset of artificial intelligence that focuses on algorithms that can learn from data.",
    "Deep learning uses neural networks with multiple layers to model and understand complex patterns in data.",
    "Natural language processing enables computers to understand, interpret, and generate human language.",
    "Computer vision allows machines to interpret and understand visual information from the world."
]

def main():
    print("Initializing FAISS Semantic Search...")
    faiss_search = FaissSemanticSearch()
    faiss_search.build_index()
    results = faiss_search.search("motorcycle")
    print(f"Found {len(results)} results for 'motorcycle'.")

    print("\nInitializing Langchain Watsonx Retriever...")
    langchain_retriever = LangchainWatsonxRetriever(project_id="skills-network")
    embeddings = langchain_retriever.get_embeddings()
    
    docs = [LC_Document(page_content="A document about email policy in the company.")]
    chunks = langchain_retriever.split_text(docs)
    
    # Example using chroma
    vectordb = Chroma.from_documents(chunks, embeddings)
    retriever = vectordb.as_retriever()
    lc_results = retriever.invoke("email policy")
    print(f"Langchain results: {len(lc_results)} documents.")

    print("\nInitializing LlamaIndex Advanced Retrievers...")
    llama_retrievers = LlamaIndexAdvancedRetrievers(SAMPLE_DOCUMENTS)
    llama_results = llama_retrievers.vector_search("What is machine learning?")
    
    for idx, res in enumerate(llama_results):
        print(f"LlamaIndex Result {idx+1}: Score: {res['score']:.4f}, Text: {res['text']}")
        
if __name__ == '__main__':
    main()
