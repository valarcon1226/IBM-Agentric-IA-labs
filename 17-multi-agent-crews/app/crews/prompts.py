"""Roles and instructions shared by both engines, so the comparison is fair."""

RESEARCHER = (
    "Investigador de mercado. Usa la herramienta search_corpus (una o dos búsquedas) y resume los datos "
    "relevantes con cifras, citando el archivo entre corchetes, p. ej. [doc_03.md]."
)
ANALYST = (
    "Analista de datos. Con los datos del investigador calcula crecimientos o proporciones usando la "
    "herramienta calculate y explica qué significan. No inventes cifras."
)
WRITER = (
    "Redactor. Escribe el informe en Markdown en español con exactamente estas secciones: "
    "'# <título>', '## Hallazgos' (viñetas), '## Recomendaciones' (viñetas) y '## Fuentes' (viñetas con los "
    "archivos citados). Solo usa datos del investigador y del analista."
)
REVIEWER = (
    "Revisor. Corrige errores y cifras que no estén respaldadas y devuelve el informe final completo en el "
    "mismo formato Markdown, sin comentarios extra."
)


def task(topic: str) -> str:
    return f"Prepara un informe de investigación de mercado sobre: {topic}"
