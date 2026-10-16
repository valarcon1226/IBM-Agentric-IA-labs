# Instrucciones para un asistente de IA: instalar y correr jobHunter

> Para la persona: abre tu asistente con acceso a terminal (Claude Code, Codex, Cursor, Copilot…) dentro de esta
> carpeta y dile: **"Lee INSTALAR_CON_IA.md y sigue las instrucciones para dejarme jobHunter funcionando."**

Asistente: tu trabajo es dejar jobHunter funcionando para la persona que te habla. Sigue los pasos en orden, corre cada
comando de verificación y no pases al siguiente paso hasta que dé el resultado esperado. Todo esto se probó en un PC
limpio con Windows y Python 3.13 el 2026-10-15.

## Lo que tienes que saber antes de empezar

- jobHunter busca vacantes en LinkedIn según el CV de la persona, les pone un % de match, genera CVs a la medida (PDF)
  para las de 70%+ y abre un reporte HTML. Los modelos de IA corren con **las llaves gratis de la persona** (o con Ollama
  en su PC, si lo tiene). No usa ningún servidor ajeno.
- `main.py` es **interactivo** (usa `input()`): la primera vez entrevista a la persona sobre su CV y le pregunta qué busca.
  **Tú no puedes contestar eso por ella.** Si corres `main.py` sin una persona escribiendo, termina con
  `EOFError: EOF when reading a line`. Por eso el paso 5 lo corre la persona en su propia terminal.
- No modifiques el código. No muestres, copies ni subas a ningún lado el `.env` (tiene sus llaves) ni nada de `Profiles/`.

## Paso 1 · Python 3.11 o más nuevo

| Sistema | Comando para verificar | Esperado |
|---|---|---|
| Windows | `py --version` | `Python 3.11` o mayor |
| macOS / Linux | `python3 --version` | `Python 3.11` o mayor |

Si no está o es más viejo: pídele a la persona que lo instale desde https://www.python.org/downloads/ (en Windows,
marcar **"Add Python to PATH"**) y vuelve a verificar. En Windows, si `python` dice *"Python was not found… Microsoft
Store"*, usa `py` en su lugar.

En el resto de esta guía, `PY` significa el Python del entorno virtual del paso 2:
`venv\Scripts\python` en Windows, `venv/bin/python` en macOS/Linux.

## Paso 2 · Entorno virtual y dependencias (~5 min)

Desde la carpeta `jobHunter` (la que tiene `main.py`):

```
py -m venv venv                       # macOS/Linux: python3 -m venv venv
PY -m pip install --upgrade pip
PY -m pip install -r requirements.txt
PY -m playwright install chromium     # ~120 MB; se usa solo para convertir los CVs a PDF
```

Esperado: el `pip install` termina con `Successfully installed …` y código de salida 0.
Si falla por un conflicto de `numpy` con `python-jobspy`: `PY -m pip install --no-deps python-jobspy` y repite el
`pip install -r requirements.txt`.

**Verificar** (sin red ni llaves; imprime `ok`):

```
PY test_location_filter.py
```

## Paso 3 · Carpeta de la persona y su CV

1. Pregúntale su **nombre y apellido** (así se llamará su carpeta) y dónde está su **hoja de vida en PDF**.
2. Copia el PDF a `Profiles/<Nombre Apellido>/` (crea las carpetas si no existen). Ejemplo:
   `Profiles/Ana Gomez/Hoja de vida Ana Gomez.pdf`. Debe ser **PDF** y no puede estar dentro de `CVs_Listos/`.

## Paso 4 · Llaves de IA (gratis, sin tarjeta)

Pídele que saque **al menos una** (con dos rinde más el cupo diario) y que te la pegue:

- Gemini: https://aistudio.google.com/apikey
- Groq: https://console.groq.com/keys
- OpenRouter (opcional): https://openrouter.ai/keys

Escríbelas en `Profiles/<Nombre Apellido>/.env`, una por línea, solo las que te dio:

```
GEMINI_API_KEY=...
GROQ_API_KEY=...
OPENROUTER_API_KEY=...
```

Con ese archivo, `main.py` ya no pide llaves. No repitas la llave en tus respuestas.
*(Opcional: si su PC tiene tarjeta de video con 4 GB o más, instalar https://ollama.com y correr `ollama pull qwen3:4b`;
`main.py` lo detecta solo y ahorra cupo de las llaves.)*

## Paso 5 · Primera corrida — LA HACE LA PERSONA, en su terminal

Dale este comando exacto (con la ruta y el nombre reales) para que lo corra en una terminal suya, no en la tuya:

```
cd "<ruta a jobHunter>"
venv\Scripts\python main.py "Nombre Apellido"        # macOS/Linux: venv/bin/python main.py "Nombre Apellido"
```

Explícale qué va a pasar:
1. **Entrevista**: lee su CV y le hace preguntas (métricas, salario, modalidad…). Puede escribir varias líneas; **Enter
   dos veces** envía la respuesta; escribir `salir` termina la entrevista.
2. **Preferencias**: país, tipos de rol (números separados por coma, p. ej. `4,6`), años de experiencia, si busca solo
   remoto, si acepta ser contractor para empresas de afuera, idiomas (`en,es`).
3. Busca vacantes (hasta ~30 min), genera hasta 10 CVs y abre el reporte en el navegador.

Que te avise cuando termine o si aparece un error (que te pegue el texto).

## Paso 6 · Verificar que quedó funcionando

En `Profiles/<Nombre Apellido>/` deben existir:

| Archivo | Qué es |
|---|---|
| `master_profile.json`, `search_settings.json` | Su perfil y lo que busca (salen del paso 5) |
| `jobs.db` | Vacantes evaluadas |
| `reporte_vacantes.html` | El reporte (ábrelo para revisar) |
| `CVs_Listos/*.pdf` | CVs a la medida (solo si hubo vacantes de 70%+) |

## Corridas siguientes (estas sí las puedes correr tú)

Con `master_profile.json` y `search_settings.json` ya creados, la única pregunta es "¿Hay cambios?". Para buscar de
nuevo sin cambios:

```
echo n | PY main.py "Nombre Apellido"
PY main.py "Nombre Apellido" --reporte      # solo vuelve a generar y abrir el reporte, sin buscar
```

Si la persona cambió de CV o de lo que busca, eso vuelve a ser entrevista: que corra el paso 5 ella misma y responda `s`.

## Si algo falla

| Mensaje | Qué hacer |
|---|---|
| `EOFError: EOF when reading a line` | Corriste un paso interactivo sin persona. Primera vez o cambios → paso 5 lo corre ella. |
| `No encontré tu CV…` | Falta el PDF en `Profiles/<Nombre Apellido>/` (paso 3), o el nombre no coincide con la carpeta. |
| `Sin al menos una llave no se puede continuar` | Falta el `.env` del paso 4 o está vacío. |
| `No se pudo crear el perfil` | Llave inválida o PDF sin texto (escaneado). Verifica la llave; si el PDF es una imagen, pide uno exportado desde Word/Docs. |
| `[CUOTA AGOTADA]` / `[FALLBACK] … sin cuota` | Cupo diario gratis agotado. Agregar otra llave al `.env` o correr al día siguiente. |
| `No se pudieron generar los CVs` | `PY -m playwright install chromium`. |
| `Python was not found` (Windows) | Usa `py` en vez de `python`, o instala Python (paso 1). |

Instrucciones para personas, sin IA: `COMO_USARLO.md`.
