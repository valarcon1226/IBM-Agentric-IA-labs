import numpy as np
import tensorflow as tf
import tensorflow_hub as hub
import faiss
import re
from sklearn.datasets import fetch_20newsgroups

# Suppress warnings
import warnings
warnings.filterwarnings('ignore')

class FaissSemanticSearch:
    def __init__(self):
        self.embed = hub.load("https://tfhub.dev/google/universal-sentence-encoder/4")
        self.index = None
        self.processed_documents = []
        self.documents = []

    def preprocess_text(self, text):
        text = re.sub(r'^From:.*\n?', '', text, flags=re.MULTILINE)
        text = re.sub(r'\S*@\S*\s?', '', text)
        text = re.sub(r'[^a-zA-Z\s]', '', text)
        text = text.lower()
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def embed_text(self, text_list):
        return self.embed(text_list).numpy()

    def build_index(self):
        newsgroups = fetch_20newsgroups(subset='all')
        self.documents = newsgroups.data[:500]  # Subset for performance
        self.processed_documents = [self.preprocess_text(doc) for doc in self.documents]
        
        embeddings = np.vstack([self.embed_text([doc]) for doc in self.processed_documents])
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings)

    def search(self, query_text, k=5):
        if not self.index:
            raise ValueError("Index not built yet.")
        preprocessed_query = self.preprocess_text(query_text)
        query_vector = self.embed_text([preprocessed_query])
        distances, indices = self.index.search(query_vector.astype('float32'), k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            results.append({
                "rank": i + 1,
                "distance": distances[0][i],
                "document": self.documents[idx]
            })
        return results


# Langchain & Watsonx
from ibm_watsonx_ai.foundation_models import ModelInference
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams
from ibm_watsonx_ai.foundation_models.extensions.langchain import WatsonxLLM
from langchain.text_splitter import RecursiveCharacterTextSplitter
from ibm_watsonx_ai.metanames import EmbedTextParamsMetaNames
from langchain_ibm import WatsonxEmbeddings

class LangchainWatsonxRetriever:
    def __init__(self, project_id, url="https://us-south.ml.cloud.ibm.com"):
        self.project_id = project_id
        self.url = url
    
    def get_llm(self):
        parameters = {
            GenParams.MAX_NEW_TOKENS: 256,
            GenParams.TEMPERATURE: 0.5,
        }
        model = ModelInference(
            model_id='mistralai/mistral-small-3-1-24b-instruct-2503',
            params=parameters,
            credentials={"url": self.url},
            project_id=self.project_id
        )
        return WatsonxLLM(model=model)

    def get_embeddings(self):
        embed_params = {
            EmbedTextParamsMetaNames.TRUNCATE_INPUT_TOKENS: 3,
            EmbedTextParamsMetaNames.RETURN_OPTIONS: {"input_text": True},
        }
        return WatsonxEmbeddings(
            model_id="ibm/slate-125m-english-rtrvr-v2",
            url=self.url,
            project_id=self.project_id,
            params=embed_params,
        )

    def split_text(self, data, chunk_size=200, chunk_overlap=20):
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )
        return splitter.split_documents(data)


# LlamaIndex
from llama_index.core import VectorStoreIndex, Document, Settings
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

class LlamaIndexAdvancedRetrievers:
    def __init__(self, documents_text):
        self.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
        Settings.embed_model = self.embed_model
        
        self.documents = [Document(text=text) for text in documents_text]
        self.vector_index = VectorStoreIndex.from_documents(self.documents)

    def vector_search(self, query, top_k=3):
        retriever = VectorIndexRetriever(
            index=self.vector_index,
            similarity_top_k=top_k
        )
        nodes = retriever.retrieve(query)
        return [{"score": node.score, "text": node.text} for node in nodes]
