import json
import os
import sys
import datetime
from typing import List, Dict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

import database
import llm_chain
from freelance_scraper import fetch_all_gigs
from freelance_hunter_agent import _BLOCKLIST

MIN_MENTIONS = 2  # una tendencia con 1 sola mención es un gig suelto, no demanda del mercado


def market_gigs(gigs: List[Dict]) -> List[Dict]:
    """Deja solo los gigs que dicen algo del mercado: sin rubros bloqueados (cripto, ventas...) y sin
    bounties de GitHub, que son issues sueltos de un repo y llenaban el reporte con tendencias de 1 mención."""
    return [g for g in gigs if g["platform"] != "GitHub Bounty"
            and not _BLOCKLIST.search(f"{g['title']} {g['description']}")]

# ==========================================
# AGENTE: Trend Spotter
# NO busca trabajo para nadie. Su único trabajo es leer QUÉ NECESITA la gente
# (patrones recurrentes en el mercado freelance) para que esa señal alimente
# qué producto/agente de automatización construir después. Inteligencia de
# mercado, no aplicación personal — esa lógica vive en freelance_hunter_agent.py.
# ==========================================

class TrendItem(BaseModel):
    trend_name: str = Field(description="Nombre descriptivo de la tendencia")
    demand_mentions: int = Field(description="Cuantos gigs del batch mencionan algo relacionado")
    estimated_automation_score: str = Field(description="Alta, Media o Baja")
    agent_idea: str = Field(description="Idea breve de como construir un agente en Python para resolverlo pasivamente")

class TrendReport(BaseModel):
    trends: List[TrendItem] = Field(description="Top 5 tendencias/micro-nichos identificados")

TRENDS_SYSTEM_PROMPT = """Eres un analista de mercado experto en encontrar micro-nichos rentables para automatizacion con IA.
Agrupa los gigs similares e identifica las 5 TENDENCIAS o MICRO-TAREAS mas solicitadas en el batch.
Para cada una, evalua que tan facil seria construir un "Agente de IA" (script Python, LLM, RPA) que la resuelva 100% solo.
No filtres por si el usuario podria o no hacerlo personalmente — este analisis es sobre EL MERCADO, no sobre una persona."""
TRENDS_HUMAN_TEMPLATE = "DATOS DEL MERCADO ({count} gigs):\n{payload}"

BATCH_SIZE = 12  # tamaño de lote conservador para no exceder el tope de tokens/minuto de ningun
# proveedor de la cadena (llm_chain.py) incluso si algo mas esta consumiendo el mismo cupo a la vez.

CONSOLIDATE_SYSTEM_PROMPT = """Eres un analista de mercado. Te paso una lista cruda de tendencias detectadas por batch
(pueden repetirse o ser variaciones del mismo micro-nicho, ej. "Chatbot de soporte" y "Chatbots de atencion al cliente").
Fusiona las que sean el mismo tema real, SUMANDO sus demand_mentions al fusionarlas, y quedate con las
TOP 10 tendencias finales ordenadas por demand_mentions descendente. Conserva la mejor agent_idea de las que fusiones
(o mejorala combinando las ideas si aplica). No inventes tendencias que no esten en la lista cruda."""
CONSOLIDATE_HUMAN_TEMPLATE = "TENDENCIAS CRUDAS ({count} entradas, de {n_batches} batches distintos):\n{payload}"

def consolidate_trends(raw_trends: List[TrendItem], n_batches: int) -> List[TrendItem]:
    """Funde tendencias duplicadas/similares detectadas en batches distintos en un top 10 final.
    El payload es compacto (sin descripciones completas) para que quepa en una sola llamada
    incluso con decenas de entradas crudas."""
    if not raw_trends:
        return []
    if len(raw_trends) <= 10:
        # Con pocas entradas no vale la pena gastar otra llamada de LLM: ya son manejables.
        return sorted(raw_trends, key=lambda t: t.demand_mentions, reverse=True)
    payload = json.dumps([t.model_dump() for t in raw_trends], ensure_ascii=False)
    try:
        report = llm_chain.invoke_structured(
            system_prompt=CONSOLIDATE_SYSTEM_PROMPT,
            human_template=CONSOLIDATE_HUMAN_TEMPLATE,
            variables={"count": len(raw_trends), "n_batches": n_batches, "payload": payload},
            pydantic_model=TrendReport,
            temperature=0.2,
        )
        return report.trends
    except Exception as e:
        print(f"   [-] No se pudo consolidar tendencias ({e}). Devolviendo la lista cruda sin fusionar.")
        return sorted(raw_trends, key=lambda t: t.demand_mentions, reverse=True)[:10]

def analyze_trends_with_llm(gigs_data: List[Dict]) -> List[TrendItem]:
    """Analiza en batches, probando Gemini -> Groq -> Cerebras -> OpenRouter (llm_chain.py) para cada uno."""
    all_trends: List[TrendItem] = []
    chunks = [gigs_data[i:i + BATCH_SIZE] for i in range(0, len(gigs_data), BATCH_SIZE)]
    print(f"\n[+] Analizando {len(gigs_data)} gigs en {len(chunks)} batch(es) de hasta {BATCH_SIZE}...")
    for i, chunk in enumerate(chunks, 1):
        print(f"   [Batch {i}/{len(chunks)}] {len(chunk)} gigs...")
        payload = json.dumps([{"platform": g["platform"], "title": g["title"], "description": g["description"][:300]} for g in chunk], ensure_ascii=False)
        try:
            report = llm_chain.invoke_structured(
                system_prompt=TRENDS_SYSTEM_PROMPT,
                human_template=TRENDS_HUMAN_TEMPLATE,
                variables={"count": len(chunk), "payload": payload},
                pydantic_model=TrendReport,
                temperature=0.2,
            )
            all_trends.extend(report.trends)
        except llm_chain.AllProvidersExhausted:
            print(f"\n[CUOTA AGOTADA] Los 4 proveedores (Gemini/Groq/Cerebras/OpenRouter) se quedaron sin cupo "
                  f"en el batch {i}/{len(chunks)}. Deteniendo con lo detectado hasta ahora ({len(all_trends)} tendencias). "
                  f"Vuelve a correr este script cuando la cuota reponga.")
            break
        except Exception as e:
            print(f"   [-] Error analizando batch {i}: {e}")
    return all_trends

def generate_markdown_report(trends: List[TrendItem], total_analyzed: int, platforms: List[str]) -> str:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    os.makedirs("trend_reports", exist_ok=True)
    filename = f"trend_reports/market_trends_{timestamp}.md"

    md = f"# Reporte de Tendencias de Mercado (Trend Spotter)\n\n"
    md += f"**Fecha:** {date_str}\n"
    md += f"**Gigs analizados en esta corrida:** {total_analyzed}\n"
    md += f"**Plataformas activas:** {', '.join(platforms) if platforms else 'ninguna'}.\n\n"
    md += "## Top nichos automatizables identificados\n\n"
    if trends:
        for idx, t in enumerate(trends, 1):
            md += f"### {idx}. {t.trend_name}\n"
            md += f"- **Menciones/Demanda:** {t.demand_mentions}\n"
            md += f"- **Viabilidad de Automatización:** {t.estimated_automation_score}\n"
            md += f"- **Idea para el Agente:** {t.agent_idea}\n\n"
    else:
        md += "_No se pudieron identificar tendencias esta corrida._\n"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[!] Reporte generado: {filename}")
    return filename

def main():
    print("====================================================")
    print(" TREND SPOTTER AGENT - Inteligencia de Mercado       ")
    print(" (qué necesita la gente -> qué agente construir)     ")
    print("====================================================\n")

    database.init_db()

    fetched = fetch_all_gigs()
    all_gigs = market_gigs(fetched)
    print(f"[i] {len(fetched)} gigs recolectados, {len(all_gigs)} relevantes para el análisis de mercado.")
    if not all_gigs:
        print("[-] No se pudo recolectar data de mercado. Abortando.")
        return

    print(f"[i] Proveedores LLM disponibles ahora: {', '.join(llm_chain.active_providers())}\n")

    raw_trends = analyze_trends_with_llm(all_gigs)
    n_batches = -(-len(all_gigs) // BATCH_SIZE)  # ceil division
    print(f"\n[+] Consolidando {len(raw_trends)} tendencias crudas de {n_batches} batch(es) en un top 10 final...")
    trends = [t for t in consolidate_trends(raw_trends, n_batches) if t.demand_mentions >= MIN_MENTIONS]

    for t in trends:
        database.save_trend(
            trend_name=t.trend_name, demand_mentions=t.demand_mentions,
            estimated_automation_score=t.estimated_automation_score,
            agent_idea=t.agent_idea, gigs_analyzed=len(all_gigs)
        )
    platforms_seen = sorted({g["platform"] for g in all_gigs})
    generate_markdown_report(trends, len(all_gigs), platforms_seen)

    print(f"\n====================================================")
    print(f" Listo. {len(trends)} tendencias consolidadas (de {len(raw_trends)} crudas) guardadas en jobs.db (tabla market_trends).")
    print(f" Total histórico de observaciones: {len(database.get_recent_trends(limit=10000))}")
    print(f"====================================================")

if __name__ == "__main__":
    main()
