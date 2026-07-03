import warnings
warnings.filterwarnings('ignore')

from langchain.document_loaders import TextLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.prompts import PromptTemplate
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory

from ibm_watsonx_ai.foundation_models import Model
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams
from ibm_watsonx_ai.foundation_models.utils.enums import DecodingMethods
from ibm_watson_machine_learning.foundation_models.extensions.langchain import WatsonxLLM
import wget
import os

def setup_rag_agent(url, filename, api_key=None):
    """
    Sets up the RAG agent by downloading the document, chunking it, creating embeddings,
    and returning a conversational chain with memory.
    """
    print(f"Downloading {filename}...")
    if not os.path.exists(filename):
        wget.download(url, out=filename)
    print("\nFile downloaded and ready.")

    # 1. Load the document
    print("Loading document...")
    loader = TextLoader(filename)
    documents = loader.load()

    # 2. Split the document into chunks
    print("Splitting document...")
    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
    texts = text_splitter.split_documents(documents)

    # 3. Embedding and storing
    print("Creating embeddings and storing in Chroma...")
    embeddings = HuggingFaceEmbeddings()
    docsearch = Chroma.from_documents(texts, embeddings)

    # 4. LLM model construction (using IBM watsonx.ai)
    print("Initializing LLM...")
    model_id = 'mistralai/mistral-small-3-1-24b-instruct-2503'
    # Another option: 'ibm/granite-4-h-small'

    parameters = {
        GenParams.DECODING_METHOD: DecodingMethods.GREEDY,  
        GenParams.MAX_NEW_TOKENS: 256,  
        GenParams.TEMPERATURE: 0.5 
    }

    credentials = {
        "url": "https://us-south.ml.cloud.ibm.com"
    }
    if api_key:
        credentials["api_key"] = api_key

    project_id = "skills-network"

    model = Model(
        model_id=model_id,
        params=parameters,
        credentials=credentials,
        project_id=project_id
    )

    llama_3_llm = WatsonxLLM(model=model)

    # 5. Integrating LangChain with Memory (Conversational Retrieval)
    memory = ConversationBufferMemory(memory_key="chat_history", return_message=True)
    
    # Optional prompt template to avoid hallucinations
    prompt_template = """Use the information from the document to answer the question at the end. If you don't know the answer, just say that you don't know, definitely do not try to make up an answer.

{context}

Question: {question}
"""
    PROMPT = PromptTemplate(
        template=prompt_template, input_variables=["context", "question"]
    )

    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llama_3_llm, 
        chain_type="stuff", 
        retriever=docsearch.as_retriever(), 
        memory=memory, 
        get_chat_history=lambda h : h, 
        combine_docs_chain_kwargs={"prompt": PROMPT},
        return_source_documents=True # From Exercise 2
    )
    
    return qa_chain

def run_agent():
    # You can also use the stateOfUnion.txt from Exercise 1
    # url = 'https://cf-courses-data.s3.us.cloud-object-storage.appdomain.cloud/XVnuuEg94sAE4S_xAsGxBA.txt'
    # filename = 'stateOfUnion.txt'
    
    url = 'https://cf-courses-data.s3.us.cloud-object-storage.appdomain.cloud/6JDbUb_L3egv_eOkouY71A.txt'
    filename = 'companyPolicies.txt'
    
    # Important: If you are running locally outside of Skills Network, provide your IBM watsonx API key here.
    api_key = None 
    
    qa_chain = setup_rag_agent(url, filename, api_key)
    
    print("\n" + "="*50)
    print("Agent is ready! Ask questions about the document.")
    print("Type 'quit', 'exit', or 'bye' to stop.")
    print("="*50 + "\n")
    
    history = []
    while True:
        query = input("Question: ")
        
        if query.lower() in ["quit", "exit", "bye"]:
            print("Answer: Goodbye!")
            break
            
        result = qa_chain.invoke({"question": query, "chat_history": history})
        
        history.append((query, result["answer"]))
        print(f"\nAnswer: {result['answer']}")
        
        # Uncomment to print source documents (Exercise 2)
        # if 'source_documents' in result:
        #     print("\nSource Context:")
        #     for doc in result['source_documents']:
        #         print(f"- {doc.page_content[:200]}...")
        print("-" * 50)

if __name__ == "__main__":
    run_agent()
