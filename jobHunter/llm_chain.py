"""
Cadena de fallback de LLMs gratuitos, compartida por todos los agentes del proyecto.

Orden: Gemini -> Groq -> Cerebras -> OpenRouter (:free). Si uno se queda sin cuota diaria
o falla, salta automaticamente al siguiente EN LA MISMA LLAMADA, en vez de crashear o de
descartar en silencio lo que se estaba evaluando. Solo levanta AllProvidersExhausted si
los 4 fallan — ahi si no queda nada mas que hacer.

Cerebras y OpenRouter son opcionales: si CEREBRAS_API_KEY / OPENROUTER_API_KEY no estan
en el .env, esos dos escalones se saltan solos (sin romper nada) y la cadena queda como
Gemini -> Groq, igual que antes.

Cuotas gratis reales (verificadas, sin tarjeta):
  Gemini:      20 requests/dia         (gemini-3.6-flash)
  Groq:        200,000 tokens/dia      (openai/gpt-oss-120b)
  OpenRouter:  50 requests/dia         (modelos con sufijo :free)

PRESUPUESTO LOCAL — VENTANA MOVIL 24H (2026-09-21): este módulo lleva la cuenta de cada llamada
(proveedor, timestamp, tokens aprox.) en la tabla `llm_usage_events` dentro de jobs.db. Antes de
llamar a un proveedor revisa cuántas llamadas/tokens caen en las últimas 24h — si ya está al
tope, lo salta SIN llamarlo. A diferencia de un contador que resetea a medianoche, esto es una
ventana que se va liberando sola a medida que pasan las horas (la llamada de hace 23h59m ya no
cuenta dentro de un minuto), así que nunca hay que "esperar hasta mañana": siempre hay un
próximo hueco calculable con `seconds_until_next_slot()`. Esto es lo que permite que un daemon
(ver `run_tailor_daemon` en tailor_agent.py) corra indefinidamente sin pararse: cuando los 4
proveedores están al tope, no falla — duerme exactamente hasta que se libera el próximo hueco y
reintenta. Los topes usados son un poco menores a los reales (ver DAILY_BUDGETS) para dejar
margen a otros agentes o a una corrida manual el mismo día.

NOTA (2026-09-19): Cerebras queda en el codigo pero DESACTIVADO a proposito — desde agosto/2026
ya no tiene tier gratis sin tarjeta (pide metodo de pago verificado incluso para los $5 de
credito gratis), asi que no cumple la regla de "no pagar nada" de este proyecto. Si en algun
momento se decide agregar la tarjeta igual, con solo poner CEREBRAS_API_KEY en el .env se
activa solo, sin tocar este archivo.
"""
import os
import sqlite3
import time
from typing import Type, TypeVar, Optional

from pydantic import BaseModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.exceptions import OutputParserException
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

import profile_paths

load_dotenv()

T = TypeVar("T", bound=BaseModel)


class AllProvidersExhausted(Exception):
    """Se lanza cuando Gemini, Groq, Cerebras Y OpenRouter fallan (cuota agotada u otro error).
    No queda ningun proveedor gratis mas al que saltar."""
    pass


def _is_quota_error(e: Exception) -> bool:
    if isinstance(e, OutputParserException):
        return False  # su mensaje incluye la respuesta entera del modelo -> falsos positivos
    s = str(e).lower()
    markers = [
        "resource_exhausted", "429", "rate_limit_exceeded", "rate limit",
        "tokens per day", "tpd", "quota", "insufficient_quota", "too many requests",
    ]
    return any(m in s for m in markers)


def _is_transient_error(e: Exception) -> bool:
    """Errores de cupo compartido que suelen resolverse solos en segundos (a diferencia de un
    cupo diario agotado, que no vuelve hasta el reset)."""
    s = str(e).lower()
    return "retry shortly" in s or "temporarily rate-limited" in s or "try again in" in s


# ---------------------------------------------------------------------------
# PRESUPUESTO DIARIO LOCAL — evita gastar cupo real llamando a un proveedor que
# ya sabemos que va a fallar hoy, y deja margen para que no se acabe del todo.
# ---------------------------------------------------------------------------

# (tope de requests/día, tope de tokens/día) — cualquiera de los dos en None = no se aplica ese eje.
# Un poco por debajo del cupo real documentado arriba, a propósito.
DAILY_BUDGETS = {
    "Gemini":     (18, None),
    "Groq":       (None, 180_000),
    "Cerebras":   (4, None),
    "OpenRouter": (45, None),
}


WINDOW_SECONDS = 24 * 3600


def _usage_db_path() -> str:
    return profile_paths.resolve("jobs.db")


def _ensure_usage_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_usage_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            ts REAL NOT NULL,
            tokens INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_usage_provider_ts ON llm_usage_events(provider, ts)")


def _record_usage(provider: str, tokens: int = 0):
    conn = sqlite3.connect(_usage_db_path())
    try:
        _ensure_usage_table(conn)
        conn.execute(
            "INSERT INTO llm_usage_events (provider, ts, tokens) VALUES (?, ?, ?)",
            (provider, time.time(), tokens),
        )
        # limpieza oportunista: eventos de hace más de 48h ya no le sirven a nadie
        conn.execute("DELETE FROM llm_usage_events WHERE ts < ?", (time.time() - 2 * WINDOW_SECONDS,))
        conn.commit()
    finally:
        conn.close()


def _get_window_usage(provider: str) -> tuple:
    """(requests, tokens) del proveedor dentro de las últimas 24h."""
    conn = sqlite3.connect(_usage_db_path())
    try:
        _ensure_usage_table(conn)
        row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(tokens), 0) FROM llm_usage_events WHERE provider = ? AND ts > ?",
            (provider, time.time() - WINDOW_SECONDS),
        ).fetchone()
        return (row[0], row[1]) if row else (0, 0)
    finally:
        conn.close()


def _budget_available(provider: str) -> bool:
    caps = DAILY_BUDGETS.get(provider)
    if not caps:
        return True
    req_cap, tok_cap = caps
    requests, tokens = _get_window_usage(provider)
    if req_cap is not None and requests >= req_cap:
        return False
    if tok_cap is not None and tokens >= tok_cap:
        return False
    return True


def seconds_until_next_slot(provider: str) -> float:
    """Cuánto falta para que se libere un hueco en la ventana de 24h de este proveedor.
    0 si ya hay cupo disponible ahora mismo."""
    if _budget_available(provider):
        return 0.0
    conn = sqlite3.connect(_usage_db_path())
    try:
        _ensure_usage_table(conn)
        oldest = conn.execute(
            "SELECT MIN(ts) FROM llm_usage_events WHERE provider = ? AND ts > ?",
            (provider, time.time() - WINDOW_SECONDS),
        ).fetchone()[0]
        if oldest is None:
            return 0.0
        return max(0.0, (oldest + WINDOW_SECONDS) - time.time())
    finally:
        conn.close()


def _local_llm_enabled() -> bool:
    return bool(os.environ.get("OLLAMA_MODEL", "").strip())


def seconds_until_any_slot() -> float:
    """El menor tiempo de espera entre todos los proveedores configurados — cuánto hay que
    dormir como mucho antes de que ALGUNO tenga cupo de nuevo. 0 si hay Ollama local (sin tope)."""
    if _local_llm_enabled():
        return 0.0
    waits = [seconds_until_next_slot(name) for name in DAILY_BUDGETS]
    return min(waits) if waits else 0.0


def any_budget_available() -> bool:
    return _local_llm_enabled() or any(_budget_available(name) for name in DAILY_BUDGETS)


def _estimate_tokens(*texts: str) -> int:
    """Heurística rápida (chars/4) para no depender de que cada proveedor devuelva usage_metadata."""
    total_chars = sum(len(t) for t in texts if t)
    return max(1, total_chars // 4) + 500  # +500 como margen para la respuesta generada


def print_budget_status():
    """Imprime cuánto cupo local queda en las últimas 24h por proveedor. Los agentes lo llaman
    al arrancar un batch para saber con qué están trabajando antes de comprometerse a correr."""
    print("[PRESUPUESTO LLM - ventana móvil 24h]")
    for name in DAILY_BUDGETS:
        req_cap, tok_cap = DAILY_BUDGETS[name]
        requests, tokens = _get_window_usage(name)
        parts = []
        if req_cap is not None:
            parts.append(f"{requests}/{req_cap} requests")
        if tok_cap is not None:
            parts.append(f"{tokens:,}/{tok_cap:,} tokens (aprox.)")
        wait = seconds_until_next_slot(name)
        wait_note = "" if wait <= 0 else f" — próximo hueco en {int(wait // 60)} min"
        print(f"   - {name}: {' | '.join(parts) if parts else 'sin límite configurado'}{wait_note}")


def _gemini():
    return ChatGoogleGenerativeAI(model="gemini-3.6-flash", temperature=0.1)


def _groq():
    return ChatGroq(model="openai/gpt-oss-120b", temperature=0.1)


def _cerebras():
    key = os.environ.get("CEREBRAS_API_KEY", "").strip()
    if not key:
        return None
    return ChatOpenAI(model="gpt-oss-120b", base_url="https://api.cerebras.ai/v1", api_key=key, temperature=0.1)


def _openrouter():
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        return None
    # NOTA (2026-09-20): el slug de deepseek-v4-flash-0731:free quedó deprecado a solo-pago
    # (OpenRouter devolvía 404 sugiriendo la versión paga). Cambiado a un modelo gratis vigente
    # verificado contra GET https://openrouter.ai/api/v1/models — revisar esa lista si este
    # también deja de estar disponible.
    return ChatOpenAI(model="google/gemma-4-31b-it:free", base_url="https://openrouter.ai/api/v1",
                       api_key=key, temperature=0.1)


def _ollama():
    # NOTA (2026-09-24): último escalón, local y SIN cupo diario — pensado para el homelab
    # (GTX 1050 4GB, qwen3:4b ~22 tok/s 100% GPU). Solo se activa si OLLAMA_MODEL está en el
    # .env, así que en la laptop la cadena queda igual que antes. Con esto el daemon nunca
    # tiene que dormir esperando cupo: si las 4 APIs gratis están al tope, cae acá.
    model = os.environ.get("OLLAMA_MODEL", "").strip()
    if not model:
        return None
    from langchain_ollama import ChatOllama
    return ChatOllama(
        model=model,
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        # 4096 = el modelo entra 100% en los 4GB de VRAM. Con 8192 se derrama 20% a CPU y cae de
        # ~22 a ~3 tok/s. El prompt del scout (perfil + JD) mide ~2400 tokens, entra de sobra.
        num_ctx=int(os.environ.get("OLLAMA_NUM_CTX", "4096")),
        num_predict=int(os.environ.get("OLLAMA_NUM_PREDICT", "1500")),  # corta si entra en loop
        reasoning=False,
        temperature=0.1,
    )


# (nombre, builder, soporta .with_structured_output() de forma confiable)
# Solo Gemini probó ser confiable con structured_output en este proyecto; el resto usa
# PydanticOutputParser + JSON forzado por prompt (mismo patron que ya usan scout/tailor).
_CHAIN = [
    ("Gemini", _gemini, True),
    ("Groq", _groq, False),
    ("Cerebras", _cerebras, False),
    ("OpenRouter", _openrouter, False),
    ("Ollama", _ollama, False),  # sin entrada en DAILY_BUDGETS -> sin tope
]

# Limites de requests/minuto conocidos (None = no se ha documentado un tope estricto en este
# proyecto). Cerebras es el unico con un RPM realmente bajo (5) pese a tener el pool de tokens
# mas grande, asi que se espacían las llamadas para no chocar ese techo innecesariamente.
_RPM_LIMITS = {"Gemini": 15, "Groq": None, "Cerebras": 5, "OpenRouter": 20}
_last_call_time = {}


def _pace(name: str):
    limit = _RPM_LIMITS.get(name)
    if not limit:
        return
    min_interval = 60.0 / limit
    last = _last_call_time.get(name, 0.0)
    elapsed = time.time() - last
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _last_call_time[name] = time.time()


def _set_temperature(llm, temperature: float):
    try:
        llm.temperature = temperature
    except Exception:
        pass


def invoke_structured(system_prompt: str, human_template: str, variables: dict,
                       pydantic_model: Type[T], temperature: float = 0.1,
                       allow_local: bool = True) -> T:
    """Invoca un prompt que debe devolver un objeto pydantic_model, probando Gemini -> Groq ->
    Cerebras -> OpenRouter en orden hasta que uno funcione. Levanta AllProvidersExhausted si
    los 4 fallan."""
    parser = PydanticOutputParser(pydantic_object=pydantic_model)
    last_error: Optional[Exception] = None
    tokens_estimate = _estimate_tokens(system_prompt, human_template, str(variables))

    for name, build_fn, structured_native in _CHAIN:
        if name == "Ollama" and not allow_local:
            # qwen3:4b sirve para no frenar, pero puntúa todo alto (85%+): para juicios donde la
            # calidad importa más que la continuidad, el llamador prefiere esperar cupo.
            continue
        if not _budget_available(name):
            print(f"   [PRESUPUESTO] {name} ya alcanzó su cupo diario reservado, saltando sin llamarlo...")
            continue
        llm = build_fn()
        if llm is None:
            continue  # sin API key configurada para este proveedor -> saltar en silencio
        _set_temperature(llm, temperature)
        _pace(name)
        for attempt in (1, 2):  # 1 reintento corto si el error es un rate-limit transitorio
            try:
                if structured_native:
                    prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", human_template)])
                    chain = prompt | llm.with_structured_output(pydantic_model)
                    result = chain.invoke(variables)
                else:
                    if name == "Ollama":
                        # Salida restringida al schema exacto: con format="json" a secas
                        # qwen3:4b a veces devuelve el perfil del input en vez de la respuesta.
                        llm.format = pydantic_model.model_json_schema()
                    json_instruction =("\n\nResponde UNICAMENTE con un JSON valido que cumpla exactamente "
                                         "este formato, sin texto adicional ni markdown:\n{format_instructions}")
                    prompt = ChatPromptTemplate.from_messages([
                        ("system", system_prompt + json_instruction),
                        ("human", human_template)
                    ])
                    chain = prompt | llm | parser
                    full_vars = {**variables, "format_instructions": parser.get_format_instructions()}
                    result = chain.invoke(full_vars)
                _record_usage(name, tokens=tokens_estimate)
                return result
            except Exception as e:
                last_error = e
                if attempt == 1 and _is_transient_error(e):
                    print(f"   [ESPERA] {name} reporta rate-limit transitorio, reintentando en 12s...")
                    time.sleep(12)
                    continue
                reason = "sin cuota/rate-limited" if _is_quota_error(e) else f"{type(e).__name__}: {str(e)[:120]}"
                print(f"   [FALLBACK] {name} falló ({reason}). Probando el siguiente proveedor...")
                break

    raise AllProvidersExhausted(f"Los {len(_CHAIN)} proveedores fallaron. Último error: {last_error}")


def _content_to_text(content) -> str:
    """Algunos proveedores (ej. Gemini via langchain_google_genai) devuelven .content
    como una lista de bloques en vez de un string plano. Lo normalizamos siempre a str."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content)


def invoke_text(system_prompt: str, human_template: str, variables: dict, temperature: float = 0.2) -> str:
    """Igual que invoke_structured pero para texto plano (sin schema). Devuelve el string de la respuesta."""
    last_error: Optional[Exception] = None
    tokens_estimate = _estimate_tokens(system_prompt, human_template, str(variables))

    for name, build_fn, _structured in _CHAIN:
        if not _budget_available(name):
            print(f"   [PRESUPUESTO] {name} ya alcanzó su cupo diario reservado, saltando sin llamarlo...")
            continue
        llm = build_fn()
        if llm is None:
            continue
        _set_temperature(llm, temperature)
        _pace(name)
        for attempt in (1, 2):
            try:
                prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", human_template)])
                res = (prompt | llm).invoke(variables)
                _record_usage(name, tokens=tokens_estimate)
                return _content_to_text(res.content)
            except Exception as e:
                last_error = e
                if attempt == 1 and _is_transient_error(e):
                    print(f"   [ESPERA] {name} reporta rate-limit transitorio, reintentando en 12s...")
                    time.sleep(12)
                    continue
                reason = "sin cuota/rate-limited" if _is_quota_error(e) else f"{type(e).__name__}: {str(e)[:120]}"
                print(f"   [FALLBACK] {name} falló ({reason}). Probando el siguiente proveedor...")
                break

    raise AllProvidersExhausted(f"Los {len(_CHAIN)} proveedores fallaron. Último error: {last_error}")


def active_providers() -> list:
    """Lista los proveedores realmente disponibles ahora mismo (con API key configurada)."""
    names = []
    for name, build_fn, _ in _CHAIN:
        try:
            if build_fn() is not None:
                names.append(name)
        except Exception:
            pass
    return names
