import os
import json
import requests
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
import profile_paths

def fetch_github_repo_readme(owner: str, repo: str) -> str:
    url = f"https://api.github.com/repos/{owner}/{repo}/readme"
    headers = {"Accept": "application/vnd.github.v3.raw"}
    print(f"Fetching README for {owner}/{repo}...")
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.text
    else:
        print(f"Error fetching repo: {response.status_code}")
        return ""

def enhance_profile_with_github():
    print("Iniciando Escaneador de GitHub...")
    
    # Repositorio proporcionado
    owner = "valarcon1226"
    repo = "IBM-AGENTIC-IA"
    
    readme_content = fetch_github_repo_readme(owner, repo)
    if not readme_content:
        print("No se pudo obtener el README. Abortando.")
        return
        
    print("Analizando proyecto con LLM...")
    llm = ChatOllama(model="llama3.2", temperature=0.3)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Eres un experto perfilador de talento en IA. Lee el siguiente README de un proyecto de GitHub. "
                   "Escribe un resumen súper atractivo (máximo 3-4 líneas) del proyecto como si fuera un 'Logro de Portafolio' para un CV. "
                   "Destaca las tecnologías usadas (agentes, LLMs, Python, etc.) y el impacto. Escríbelo en primera persona ('Diseñé e implementé...')."),
        ("human", "README del Proyecto:\n\n{readme}")
    ])
    
    chain = prompt | llm
    resumen_proyecto = chain.invoke({"readme": readme_content}).content
    
    print("\nResumen Generado:")
    print(resumen_proyecto)
    
    # Update master profile
    master_path = profile_paths.resolve("master_profile.json")
    
    if os.path.exists(master_path):
        with open(master_path, "r", encoding="utf-8") as f:
            profile = json.load(f)
            
        if "portfolio_projects" not in profile:
            profile["portfolio_projects"] = []
            
        profile["portfolio_projects"].append(resumen_proyecto)
        
        with open(master_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=4)
            
        print("\n Proyecto de GitHub agregado exitosamente al master_profile.json")
    else:
        print("\n master_profile.json no encontrado.")

if __name__ == "__main__":
    enhance_profile_with_github()
