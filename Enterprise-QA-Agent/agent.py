import os
import wget
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

def download_document(url: str, filename: str) -> None:
    """Downloads a document from a given URL if it doesn't already exist."""
    if not os.path.exists(filename):
        print(f"Downloading {filename}...")
        wget.download(url, out=filename)
        print("\nFile downloaded successfully.")

def get_watsonx_llm(model_id: str = 'mistralai/mistral-small-3-1-24b-instruct-2503', api_key: str = None) -> WatsonxLLM:
    """Initializes and returns a WatsonxLLM instance."""
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

    model = Model(
        model_id=model_id,
        params=parameters,
        credentials=credentials,
        project_id="skills-network"
    )
    return WatsonxLLM(model=model)

def setup_rag_agent(url: str, filename: str, api_key: str = None) -> ConversationalRetrievalChain:
    """
    Sets up the RAG agent by downloading the document, chunking it, creating embeddings,
    and returning a conversational chain with memory.
    """
    download_document(url, filename)

    loader = TextLoader(filename)
    documents = loader.load()

    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
    texts = text_splitter.split_documents(documents)

    embeddings = HuggingFaceEmbeddings()
    docsearch = Chroma.from_documents(texts, embeddings)

    llm = get_watsonx_llm(api_key=api_key)

    memory = ConversationBufferMemory(memory_key="chat_history", return_message=True)
    
    prompt_template = """Use the information from the document to answer the question at the end. If you don't know the answer, just say that you don't know, definitely do not try to make up an answer.

{context}

Question: {question}
"""
    prompt = PromptTemplate(
        template=prompt_template, input_variables=["context", "question"]
    )

    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        chain_type="stuff",
        retriever=docsearch.as_retriever(),
        memory=memory,
        get_chat_history=lambda h: h,
        combine_docs_chain_kwargs={"prompt": prompt},
        return_source_documents=False
    )
    
    return qa_chain
