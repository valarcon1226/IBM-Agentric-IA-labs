import os
import gradio as gr
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from tools import extract_video_id, fetch_transcript, get_full_metadata, search_youtube

def get_agent(api_key: str):
    if not api_key:
        raise ValueError("Please provide a valid API Key.")
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=api_key,
        temperature=0.3
    )
    
    tools = [extract_video_id, fetch_transcript, get_full_metadata, search_youtube]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an advanced YouTube Assistant. You can search YouTube, extract video IDs, fetch transcripts, and get metadata using the provided tools. Always be helpful and format your answers clearly using markdown. If asked to summarize, fetch the transcript and provide a detailed summary. If asked about multiple videos, process each one carefully."),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True)

def chat_interface(message, history, api_key):
    if not api_key:
        yield "⚠️ Please enter your API Key in the settings first."
        return
        
    try:
        agent_executor = get_agent(api_key)
        
        chat_history = []
        for human_msg, ai_msg in history:
            chat_history.append(HumanMessage(content=human_msg))
            chat_history.append(AIMessage(content=ai_msg))
            
        response = agent_executor.invoke({
            "input": message,
            "chat_history": chat_history
        })
        
        yield response["output"]
    except Exception as e:
        yield f"Error: {str(e)}"

def batch_process(urls_text, api_key):
    if not api_key:
        return "⚠️ Please enter your API Key in the settings first."
    
    urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
    if not urls:
        return "Please provide at least one valid URL."
        
    try:
        agent_executor = get_agent(api_key)
        prompt = f"Please process the following YouTube videos and provide a structured summary for each, including its Title, Views, and a brief 2-sentence summary of its transcript:\n"
        for i, url in enumerate(urls):
            prompt += f"{i+1}. {url}\n"
            
        response = agent_executor.invoke({
            "input": prompt,
            "chat_history": []
        })
        
        return response["output"]
    except Exception as e:
        return f"Error: {str(e)}"

def main():
    custom_css = """
    .container { max-width: 1000px; margin: auto; }
    .header { text-align: center; margin-bottom: 2rem; }
    .header h1 { color: #2D3748; }
    .tab-content { padding: 20px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px; }
    """
    
    with gr.Blocks(css=custom_css, theme=gr.themes.Soft(primary_hue="indigo")) as app:
        with gr.Column(elem_classes="container"):
            gr.Markdown(
                """
                <div class="header">
                    <h1>🎬 YouTube Agentic Analyzer</h1>
                    <p>Powered by LangChain Agents & LLMs</p>
                </div>
                """
            )
            
            api_key_input = gr.Textbox(
                label="API Key", 
                placeholder="Enter your API Key...", 
                type="password",
                info="Required to run the Agent."
            )
            
            with gr.Tabs():
                with gr.TabItem("💬 Agent Chatbot"):
                    gr.ChatInterface(
                        fn=chat_interface,
                        additional_inputs=[api_key_input],
                        description="Chat with the YouTube Agent. Paste a URL and ask it to summarize, extract metadata, or answer specific questions about the video.",
                        examples=[
                            "Summarize this video: https://www.youtube.com/watch?v=3Cni6_JubQk",
                            "What is the view count and channel name for https://www.youtube.com/watch?v=T-D1OfcDW1M?",
                        ]
                    )
                    
                with gr.TabItem("📊 Batch Processing"):
                    gr.Markdown("### Analyze Multiple Videos at Once")
                    gr.Markdown("Paste a list of YouTube URLs (one per line) to automatically extract metadata and summaries for all of them in a structured format.")
                    
                    with gr.Row():
                        with gr.Column(scale=1):
                            urls_input = gr.Textbox(
                                label="YouTube URLs", 
                                placeholder="https://www.youtube.com/watch?v=...\nhttps://www.youtube.com/watch?v=...",
                                lines=10
                            )
                            batch_btn = gr.Button("🚀 Process Batch", variant="primary")
                        with gr.Column(scale=2):
                            batch_output = gr.Markdown(label="Results", value="*Results will appear here...*")
                            
                    batch_btn.click(
                        fn=batch_process,
                        inputs=[urls_input, api_key_input],
                        outputs=batch_output
                    )

    app.launch(server_name="0.0.0.0", server_port=7860)

if __name__ == '__main__':
    main()
