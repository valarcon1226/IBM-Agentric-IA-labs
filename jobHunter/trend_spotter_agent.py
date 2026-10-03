import json
import re
import os
import sys
import datetime
from collections import defaultdict
from difflib import SequenceMatcher
from typing import List, Dict, Literal

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

import database
import learning_plan
import llm_chain
from freelance_scraper import fetch_all_gigs, fetch_hustle_gigs
from freelance_hunter_agent import _BLOCKLIST

# ==========================================
# AGENTE: Trend Spotter
# Busca NICHOS VENDIBLES: tareas/problemas que el mercado paga una y otra vez (ej. "redactar
# contratos legales", "notas clínicas") para construir un agente que las resuelva y venderlo.
# No cuenta skills. Corre cada hora gratis:
#   1. El modelo LOCAL (Ollama) anota qué tarea pide cada vacante/gig — una sola vez por URL.
#   2. Python agrupa y cuenta por (dominio, tarea) — últimos 7 y 30 días.
#   3. Una vez al día, UNA llamada a la nube escribe el reporte de oportunidades.
# ==========================================

MAX_PER_RUN = int(os.environ.get("TRENDS_MAX_PER_RUN", "60"))  # no acaparar la GPU que usan scout/freelance
REPORT_EVERY_HOURS = 20
MIN_MENTIONS = 2  # 1 sola mención es un gig suelto, no demanda del mercado
SIMILAR = 0.8     # tareas del mismo dominio con este parecido se cuentan como la misma


def market_gigs(gigs: List[Dict]) -> List[Dict]:
    """Sin rubros bloqueados (cripto, ventas...) ni bounties de GitHub (issues sueltos de un repo)."""
    return [g for g in gigs if g["platform"] != "GitHub Bounty"
            and not _BLOCKLIST.search(f"{g['title']} {g['description']}")]


# Los 10 side hustles del video "10 Claude AI Side Hustles" (Patrick Dang). Valentina eligió growth operator,
# youtube agency, content distribution y seo_aeo (memoria side-hustle-picks). "otro" = no encaja en ninguno.
HUSTLES = {
    "meta_ads": "Crear o gestionar campañas de anuncios pagados en Facebook/Instagram (creativos, segmentación, escalar ads)",
    "ghostwriting": "Escribir textos con la voz de una persona o marca: posts de LinkedIn/X, newsletters, discursos, copy de ventas",
    "ai_creator": "Crear contenido propio sobre IA (videos, posts, cursos) para una audiencia",
    "growth_operator": "Operar el back-end de un creador o negocio online: funnels, landing pages, webinars, CRM, GoHighLevel/ClickFunnels",
    "youtube_agency": "Manejar un canal de YouTube existente: editar los episodios del canal, miniaturas, títulos, estrategia y publicación. NO incluye videos promocionales o comerciales sueltos",
    "content_distribution": "Recortar videos LARGOS que ya existen (podcasts, streams, episodios) en clips cortos (Shorts/Reels/TikTok) y republicarlos. NO incluye grabar ni producir videos nuevos",
    "seo_aeo": "Posicionamiento en buscadores y en IAs (SEO/GEO/AEO): auditorías, keywords, contenido optimizado, sitios en Webflow/WordPress pensados para SEO",
    "lead_generation": "Conseguir prospectos B2B: armar listas de contactos, cold email, outreach en LinkedIn",
    "dm_setting": "Responder mensajes directos y agendar llamadas de venta (appointment setting)",
    "email_marketing": "Email marketing y retención: flujos en Klaviyo/Mailchimp, campañas, carritos abandonados",
    "otro": "Cualquier otra cosa: producción de video nuevo (promos, animaciones, demos), diseño gráfico, traducción, desarrollo de software, data entry, etc.",
}
PICKED = ["growth_operator", "youtube_agency", "content_distribution", "seo_aeo"]
# El modelo local mete casi cualquier cosa en alguna categoría (p. ej. un sitio web común en growth_operator):
# cada side hustle exige su señal en el texto o pasa a "otro".
_HUSTLE_REQUIRES = {
    "content_distribution": re.compile(r"clip|short|reel|tiktok|repurpos|podcast|stream|highlight|recort", re.I),
    "youtube_agency": re.compile(r"youtube|channel|canal", re.I),
    "growth_operator": re.compile(r"funnel|embudo|crm|gohighlevel|go high level|clickfunnels|webinar|lead magnet|"
                                  r"sales page|landing|membership|course platform|kajabi|systeme|opt-?in|"
                                  r"marketing automation|creator|coach", re.I),
    "email_marketing": re.compile(r"email|e-mail|correo|klaviyo|mailchimp|newsletter|drip|abandoned cart|"
                                  r"carrito abandonado|flows?\b|sequence|retention|retenci", re.I),
    "lead_generation": re.compile(r"lead|prospect|outreach|cold|contact list|lista de contactos|b2b|apollo|"
                                  r"linkedin|sales navigator|scrap\w* (emails|contacts)", re.I),
    "meta_ads": re.compile(r"facebook ads?|instagram ads?|meta ads?|ads manager|paid (social|ads)|ad campaign|"
                           r"campaña|anuncios|ad creatives?|ppc", re.I),
    "seo_aeo": re.compile(r"seo|search engine|ranking|keyword|google search|backlink|aeo|geo\b|posicionamiento|"
                          r"serp|organic traffic", re.I),
    "ghostwriting": re.compile(r"write|writ\w+|copy|ghost|post|article|blog|newsletter|speech|script|redac|escrib", re.I),
    "ai_creator": re.compile(r"content creator|influencer|ugc|faceless|youtube|tiktok|instagram|course|curso", re.I),
    "dm_setting": re.compile(r"\bdms?\b|direct message|appointment|setter|book(ing)? calls|agendar|inbound messages", re.I),
}


def check_hustle(hustle: str, text: str) -> str:
    rule = _HUSTLE_REQUIRES.get(hustle)
    return "otro" if rule and not rule.search(text) else hustle


class DemandSignal(BaseModel):
    domain: str = Field(description="Industria del cliente, 1-2 palabras en inglés: legal, medical, real estate, ecommerce, finance, marketing, education, hr, logistics, software...")
    task: str = Field(description="La tarea repetible que el cliente necesita hecha, 3-8 palabras en inglés, genérica, sin nombres de empresas. Ej: 'draft legal contracts', 'write clinical visit notes', 'extract data from invoices'")
    deliverable: str = Field(description="Qué se entrega, pocas palabras")
    automatable: Literal["high", "medium", "low"] = Field(description="Qué tanto podría hacerlo un agente de IA solo, con revisión humana mínima")
    hustle: Literal[tuple(HUSTLES)] = Field(description="Categoría de servicio: " + "; ".join(f"{k} = {v}" for k, v in HUSTLES.items()))


EXTRACT_SYSTEM_PROMPT = """Lees un aviso de trabajo o proyecto freelance y dices QUÉ TAREA REPETIBLE necesita el cliente.
No describas el puesto ni las tecnologías: describe el trabajo que se entrega (el problema que se resuelve)."""
EXTRACT_HUMAN_TEMPLATE = "TÍTULO: {title}\nDESCRIPCIÓN: {description}"


def extract_new_signals() -> int:
    """Anota con el modelo local las vacantes/gigs que todavía no tienen señal. Nunca usa la nube."""
    fresh = [{"url": g["url"], "source": "gig", "title": g["title"], "description": g["description"]}
             for g in market_gigs(fetch_all_gigs())]
    # side hustles (marketing, video, SEO...): sin el blocklist del agente de Freelance, que descarta justo eso
    fresh += [{"url": g["url"], "source": "gig", "title": g["title"], "description": g["description"]}
              for g in fetch_hustle_gigs()]
    stored = [i for i in database.get_market_items()
              if i["source"] == "job" or not _BLOCKLIST.search(f"{i['title']} {i['description']}")]
    known = database.get_signal_urls()
    pending = list({i["url"]: i for i in fresh + stored if i["url"] and i["url"] not in known}.values())
    print(f"[i] {len(pending)} vacantes/gigs sin analizar; esta corrida procesa hasta {MAX_PER_RUN}.")

    done = 0
    for item in pending[:MAX_PER_RUN]:
        try:
            s = llm_chain.invoke_structured(
                system_prompt=EXTRACT_SYSTEM_PROMPT,
                human_template=EXTRACT_HUMAN_TEMPLATE,
                variables={"title": item["title"], "description": item["description"][:1500]},
                pydantic_model=DemandSignal,
                local_only=True,
            )
        except llm_chain.AllProvidersExhausted as e:
            print(f"[-] Modelo local no disponible ({e}). Se reintenta en la próxima corrida.")
            break
        except Exception as e:
            print(f"   [-] No se pudo analizar {item['url']}: {e}")
            continue
        database.save_signal(item["url"], item["source"], s.domain.strip().lower(),
                             s.task.strip().lower(), s.deliverable.strip(), s.automatable,
                             check_hustle(s.hustle, f"{item['title']} {item['description']} {s.task}"))
        done += 1
    return done


def group_signals(signals: List[Dict], recent_since: str = "") -> List[Dict]:
    """Agrupa por dominio y tarea parecida. count_7d cuenta las señales con extracted_at >= recent_since.
    Devuelve grupos ordenados por cantidad."""
    groups: Dict[str, List[Dict]] = defaultdict(list)  # dominio -> grupos
    for s in signals:
        domain_groups = groups[s["domain"]]
        # ponytail: comparación O(n²) por dominio; pasar a embeddings si hay miles de tareas distintas
        match = next((g for g in domain_groups
                      if SequenceMatcher(None, g["task"], s["task"]).ratio() >= SIMILAR), None)
        if match is None:
            match = {"domain": s["domain"], "task": s["task"], "count": 0, "count_7d": 0, "deliverables": set(), "automatable": defaultdict(int)}
            domain_groups.append(match)
        match["count"] += 1
        match["count_7d"] += (s.get("extracted_at") or "") >= recent_since
        match["deliverables"].add(s["deliverable"])
        match["automatable"][s["automatable"]] += 1
    flat = [g for gs in groups.values() for g in gs]
    for g in flat:
        g["automatable"] = max(g["automatable"], key=g["automatable"].get)
        g["deliverables"] = sorted(g["deliverables"])[:3]
    return sorted(flat, key=lambda g: g["count"], reverse=True)


class Opportunity(BaseModel):
    niche: str = Field(description="Nombre del nicho, ej. 'Redacción de documentos legales'")
    demand: int = Field(description="Suma de menciones de los grupos fusionados en este nicho")
    automation: Literal["Alta", "Media", "Baja"]
    agent_idea: str = Field(description="Qué hace el agente y con qué stack")
    how_to_sell: str = Field(description="Quién lo compra, cómo empaquetarlo y una idea de precio")
    review_effort: str = Field(description="Cuánta revisión humana necesita cada entrega")

class OpportunityReport(BaseModel):
    opportunities: List[Opportunity]

REPORT_SYSTEM_PROMPT = """Eres analista de negocio. Te paso grupos de tareas que el mercado (vacantes + proyectos freelance)
pide repetidamente, con cuántas veces aparecieron en 7 y 30 días. Fusiona los grupos que sean el mismo nicho (sumando demanda)
y devuelve las 10 MEJORES OPORTUNIDADES para que UNA persona construya un agente de IA que haga ese trabajo, ella revise
la salida y la entregue/venda con casi cero esfuerzo. Prioriza demanda alta, creciente y automatizable. No inventes nichos
que no estén en los datos. Escribe en español."""
REPORT_HUMAN_TEMPLATE = "GRUPOS ({count}):\n{payload}"


def build_report(top: List[Dict]) -> List[Opportunity]:
    payload = json.dumps([{"domain": g["domain"], "task": g["task"], "count_30d": g["count"],
                           "count_7d": g["count_7d"],
                           "deliverables": g["deliverables"], "automatable": g["automatable"]} for g in top],
                         ensure_ascii=False)
    try:
        return llm_chain.invoke_structured(
            system_prompt=REPORT_SYSTEM_PROMPT, human_template=REPORT_HUMAN_TEMPLATE,
            variables={"count": len(top), "payload": payload},
            pydantic_model=OpportunityReport, temperature=0.3, allow_local=False,
        ).opportunities
    except Exception as e:  # sin cupo de nube: el reporte sale igual, con los números crudos
        print(f"[-] Sin reporte de la nube ({e}). Se publica el conteo sin análisis.")
        auto = {"high": "Alta", "medium": "Media", "low": "Baja"}
        return [Opportunity(niche=f"{g['task']} ({g['domain']})", demand=g["count"], automation=auto[g["automatable"]],
                            agent_idea="(pendiente de análisis)", how_to_sell="(pendiente de análisis)",
                            review_effort="(pendiente de análisis)") for g in top[:10]]


def hustle_demand(signals: List[Dict], recent_since: str) -> List[Dict]:
    """Demanda por side hustle del video: menciones en 30 y 7 días, automatización más común y tareas típicas."""
    by = defaultdict(list)
    for s in signals:
        if s.get("hustle") and s["hustle"] != "otro":
            by[s["hustle"]].append(s)
    rows = []
    for key, items in by.items():
        auto, tasks = defaultdict(int), defaultdict(int)
        for s in items:
            auto[s["automatable"]] += 1
            tasks[s["task"]] += 1
        rows.append({"key": key, "name": HUSTLES[key], "picked": key in PICKED, "count": len(items),
                     "count_7d": sum(1 for s in items if (s.get("extracted_at") or "") >= recent_since),
                     "automatable": max(auto, key=auto.get),
                     "top_tasks": [t for t, _ in sorted(tasks.items(), key=lambda kv: -kv[1])[:3]]})
    return sorted(rows, key=lambda r: r["count"], reverse=True)


def generate_markdown_report(opps: List[Opportunity], total_signals: int, hustles: List[Dict] = ()) -> str:
    now = datetime.datetime.now()
    os.makedirs("trend_reports", exist_ok=True)
    filename = f"trend_reports/market_trends_{now:%Y%m%d_%H%M%S}.md"
    md = "# Reporte de Tendencias de Mercado (Trend Spotter)\n\n"
    md += f"**Fecha:** {now:%Y-%m-%d %H:%M}\n"
    md += f"**Vacantes y gigs analizados (30 días):** {total_signals}\n\n"
    if hustles:
        md += "## Demanda de los side hustles del video (⭐ = los que elegiste)\n\n"
        md += "| Side hustle | Menciones 30 d | Últimos 7 d | Automatización | Tareas típicas |\n|---|---|---|---|---|\n"
        for h in hustles:
            md += (f"| {'⭐ ' if h['picked'] else ''}{h['name']} | {h['count']} | {h['count_7d']} | {h['automatable']} | "
                   f"{'; '.join(h['top_tasks'])} |\n")
        md += "\n"
    md += "## Nichos para automatizar y vender\n\n"
    for i, o in enumerate(opps, 1):
        md += (f"### {i}. {o.niche}\n- **Demanda:** {o.demand} menciones\n- **Automatización:** {o.automation}\n"
               f"- **Agente:** {o.agent_idea}\n- **Cómo venderlo:** {o.how_to_sell}\n- **Revisión humana:** {o.review_effort}\n\n")
    if not opps:
        md += "_Todavía no hay suficientes datos._\n"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[!] Reporte generado: {filename}")
    return filename


def main():
    print("====================================================")
    print(" TREND SPOTTER - nichos que el mercado paga y se pueden automatizar")
    print("====================================================\n")
    database.init_db()

    print(f"[+] {extract_new_signals()} señales nuevas guardadas.")
    learning_plan.update()  # gaps de las vacantes -> qué aprender primero (pestaña "Aprender" del dashboard)

    hours = database.hours_since_last_trend()
    if hours < REPORT_EVERY_HOURS:
        print(f"[i] Último reporte hace {hours:.1f}h — el próximo sale a las {REPORT_EVERY_HOURS}h.")
        return

    month = database.get_signals(30)
    week_ago = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    top = [g for g in group_signals(month, week_ago) if g["count"] >= MIN_MENTIONS][:50]
    if not top:
        print("[i] Aún no hay tareas repetidas suficientes para un reporte.")
        return

    opps = build_report(top)
    for o in opps:
        database.save_trend(trend_name=o.niche, demand_mentions=o.demand, estimated_automation_score=o.automation,
                            agent_idea=f"{o.agent_idea}\nCómo venderlo: {o.how_to_sell}\nRevisión: {o.review_effort}",
                            gigs_analyzed=len(month))
    hustles = hustle_demand(month, week_ago)
    for h in hustles:
        database.save_trend(trend_name=f"[Side hustle] {'⭐ ' if h['picked'] else ''}{h['name']}", demand_mentions=h["count"],
                            estimated_automation_score={"high": "Alta", "medium": "Media", "low": "Baja"}[h["automatable"]],
                            agent_idea="Tareas típicas: " + "; ".join(h["top_tasks"]) + f"\nÚltimos 7 días: {h['count_7d']}",
                            gigs_analyzed=len(month))
    generate_markdown_report(opps, len(month), hustles)


if __name__ == "__main__":
    main()
