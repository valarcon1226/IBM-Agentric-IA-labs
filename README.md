# AI & LLM Engineering Portfolio

Welcome to my AI engineering portfolio. This repository contains various practical projects focusing on Large Language Models (LLMs), Retrieval-Augmented Generation (RAG), Autonomous Agents, Vector Databases, and Multimodal AI.

## Projects Included

### 1. ?? AI Agents Fundamentals (`AI-Agents-Fundamentals`)
A collection of scripts demonstrating the core principles of AI Agents using LangChain. Includes an **AI Math Assistant** that leverages tool-calling to solve complex mathematical queries step-by-step, and an **LCEL** (LangChain Expression Language) pipeline for executing data science tasks autonomously.
* **Tech Stack:** LangChain, Tool Calling, LCEL.

### 2. ??? AI Meeting Assistant (`AI-Meeting-Assistant`)
An intelligent agent designed to process meeting transcripts, summarize key points, and extract actionable action items automatically.
* **Tech Stack:** Python, LangChain, LLM Summarization.

### 3. ?? Candidate Filter (`Candidate-Filter`)
An HR simulation application that combines **Semantic Similarity Search** with exact **Metadata Filtering** to find ideal candidates.
* **Tech Stack:** Chroma DB, HuggingFace Sentence Transformers, Vector Embeddings.

### 4. ?? Document Ingestion Pipeline (`doc_ingest`)
A complete document processing and ingestion pipeline for building RAG systems. It handles parsing, chunking, and embedding documents into a Vector DB, powered by background watchdog agents that update the database when new files are added.
* **Tech Stack:** Chroma, SentenceTransformers, Watchdog, LangChain.

### 5. ?? Enterprise QA Agent (`Enterprise-QA-Agent`)
A robust RAG-based Question Answering agent tailored for enterprise documents. It allows users to query internal company policies or manuals using natural language, providing accurate answers with citations. Includes a web interface built with Gradio.
* **Tech Stack:** LangChain, Gradio, RAG.

### 6. ?? Food Search Chatbot (`Food-Search-Chatbot`)
A conversational AI chatbot that helps users find food recipes or restaurant recommendations based on semantic search through a customized dataset.
* **Tech Stack:** Python, Vector Search.

### 7. ?? Multimodal Generators (`Multimodal-Generators`)
Projects utilizing multimodal AI capabilities. Includes an **AI Storyteller** that generates narratives, and a script interacting with DALL-E (or similar models) to generate images based on text prompts.
* **Tech Stack:** Multimodal LLMs, Image Generation APIs.

### 8. ?? YouTube RAG Analyzer (`YouTube-RAG-Analyzer`)
An intelligent tool that extracts transcripts from YouTube videos and uses RAG to allow users to ask questions, generate summaries, and extract specific information directly from video content.
* **Tech Stack:** YouTube Transcript API, LangChain, RAG.

### 9. ?? Advanced RAG Techniques (`Advanced-RAG-Techniques`)
Implementations of advanced retrieval techniques to improve RAG performance, including custom retrievers using **LlamaIndex** and **FAISS**, as well as context-aware retrieval optimization.
* **Tech Stack:** LlamaIndex, FAISS, Advanced RAG.

## Setup Instructions

Each project is self-contained. Navigate to any project directory and follow the instructions in its respective `README.md` to install dependencies and run the scripts.
