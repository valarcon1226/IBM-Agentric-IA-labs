"""Unit tests for keyword cluster article categorization."""

from intelligence.nlp_processor import categorize_article

CATEGORIES = [
    {"id": "cat-ai", "name": "Inteligencia Artificial", "keywords": ["ia", "ai", "llm", "gpt", "modelos", "redes neuronales"]},
    {"id": "cat-sec", "name": "Ciberseguridad", "keywords": ["seguridad", "vulnerabilidad", "ransomware", "malware", "phishing"]},
    {"id": "cat-cloud", "name": "Cloud y DevOps", "keywords": ["cloud", "kubernetes", "docker", "devops", "aws"]},
    {"id": "cat-fin", "name": "Fintech y Mercados", "keywords": ["fintech", "mercado", "inversión", "bolsa", "acciones"]},
    {"id": "cat-gen", "name": "General", "keywords": ["tecnología", "innovación", "digital"]},
]


def test_categorize_ai_article():
    title = "Nuevo modelo GPT de OpenAI supera pruebas de razonamiento"
    content = "Investigadores presentaron avances en modelos de inteligencia artificial y redes neuronales."
    cat = categorize_article(title, content, CATEGORIES)
    assert cat["name"] == "Inteligencia Artificial"
    assert cat["id"] == "cat-ai"


def test_categorize_cybersecurity_article():
    title = "Ataque masivo de ransomware paraliza servicios"
    content = "Una vulnerabilidad de día cero permitió propagar malware mediante phishing dirigido."
    cat = categorize_article(title, content, CATEGORIES)
    assert cat["name"] == "Ciberseguridad"
    assert cat["id"] == "cat-sec"


def test_categorize_cloud_article():
    title = "Kubernetes 1.32 optimiza clusters de contenedores"
    content = "Novedades para arquitecturas cloud y despliegues devops con Docker."
    cat = categorize_article(title, content, CATEGORIES)
    assert cat["name"] == "Cloud y DevOps"
    assert cat["id"] == "cat-cloud"


def test_categorize_general_fallback():
    title = "El impacto del café en la concentración matutina"
    content = "Un estudio analiza cómo la cafeína altera los ritmos circadianos en humanos."
    cat = categorize_article(title, content, CATEGORIES)
    assert cat["name"] == "General"
