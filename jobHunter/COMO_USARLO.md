# jobHunter: encuentra vacantes y genera tu CV a la medida

Busca vacantes remotas en LinkedIn según tu perfil, les pone un % de match técnico, genera un CV adaptado para las
que superan 70% y te arma un reporte con todo (link a la oferta, tu CV y lo que te falta estudiar).
Gratis: usa tus propias llaves de IA (sin tarjeta). Por ahora es solo para empleos 9-5.

> ¿Prefieres que una IA te lo instale? Abre tu asistente (Claude Code, Codex, Cursor…) en esta carpeta y dile:
> "Lee INSTALAR_CON_IA.md y sigue las instrucciones para dejarme jobHunter funcionando."

## Instalación (una sola vez, ~15 min)

**1. Descomprime** `jobHunter.zip` donde quieras (clic derecho → *Extraer todo*). Queda una carpeta `jobHunter`.

**2. Instala Python** (3.11 o más nuevo) desde https://www.python.org/downloads/ → botón amarillo *Download*.
En Windows, en la primera pantalla del instalador **marca la casilla "Add python.exe to PATH"** antes de *Install Now*.

**3. Abre una terminal dentro de la carpeta `jobHunter`:**
- **Windows**: abre la carpeta `jobHunter` en el Explorador, haz clic en la barra de la dirección (arriba), borra lo que
  dice, escribe `powershell` y presiona Enter.
- **Mac**: abre la app *Terminal*, escribe `cd ` (con un espacio al final), arrastra la carpeta `jobHunter` a la ventana
  y presiona Enter.

Para comprobar que quedaste en el lugar correcto escribe `dir` (Windows) o `ls` (Mac) y Enter: tiene que aparecer
`main.py` en la lista.

**4. Instala lo que necesita.** Copia y pega estos comandos uno por uno (Enter después de cada uno; el segundo tarda
varios minutos y escribe mucho texto, es normal):

| Windows | Mac |
|---|---|
| `py -m venv venv` | `python3 -m venv venv` |
| `venv\Scripts\python -m pip install -r requirements.txt` | `venv/bin/python -m pip install -r requirements.txt` |
| `venv\Scripts\python -m playwright install chromium` | `venv/bin/python -m playwright install chromium` |

Si el segundo termina en rojo hablando de `numpy`, corre `venv\Scripts\python -m pip install --no-deps python-jobspy`
(Mac: `venv/bin/python …`) y repite el segundo.

**5. Saca tu llave de IA gratis** (no pide tarjeta). Con una basta; con dos rinde más:
- **Gemini**: entra a https://aistudio.google.com/apikey con tu cuenta de Google → *Create API key* → copia el código.
- **Groq**: entra a https://console.groq.com/keys (cuenta de Google o correo) → *Create API Key* → copia el código.

Guárdalas en un bloc de notas: el programa te las pide la primera vez. **No se las compartas a nadie.**

*(Opcional: si tu PC tiene buena tarjeta de video, instala [Ollama](https://ollama.com) y corre `ollama pull qwen3:4b`:
lo pesado corre en tu PC y te rinde más el cupo gratis de las llaves.)*

## Uso

**1. Pon tu CV**: dentro de `jobHunter`, crea la carpeta `Profiles` y dentro una carpeta con tu nombre. Ahí copia tu
**hoja de vida en PDF**:  `jobHunter/Profiles/Ana Gomez/Hoja de vida Ana Gomez.pdf`

**2. Corre el programa** (en la terminal del paso 3, con tu nombre igual al de la carpeta y entre comillas):

| Windows | Mac |
|---|---|
| `venv\Scripts\python main.py "Ana Gomez"` | `venv/bin/python main.py "Ana Gomez"` |

**3. La primera vez te pregunta:**
- **Tus llaves de IA**: pega cada una (en Windows, clic derecho pega en la terminal) y Enter. Enter sin escribir nada
  salta la que no tengas.
- **Una entrevista sobre tu CV** (métricas, salario, modalidad…): escribe tu respuesta, puede tener varias líneas;
  presiona **Enter dos veces** para enviarla. Escribe `salir` para terminar la entrevista.
- **Qué buscas**: país, tipos de rol (te muestra una lista numerada: escribe los números separados por coma, p. ej.
  `4,6`), años de experiencia, si buscas solo remoto, si aceptas trabajar como contractor para empresas de afuera e
  idiomas (`en,es` = inglés y español). Enter sin escribir acepta lo que sale entre `[ ]`.

**4. Espera**: busca vacantes (hasta ~30 min), genera hasta 10 CVs y **abre el reporte** en tu navegador solo.
No cierres la terminal mientras trabaja.

**Las siguientes veces**: abre la terminal en la carpeta (paso 3 de instalación) y corre el mismo comando. Solo te
pregunta si hubo cambios en tu CV o en lo que buscas (`n` + Enter si no). Agrega `--reporte` al final del comando para
solo volver a abrir el reporte sin buscar.

## Dónde queda todo (tu carpeta `Profiles/<tu nombre>/`)

| Archivo | Qué es |
|---|---|
| `reporte_vacantes.html` | El reporte: vacantes con % de match, links, CV y lo que te falta |
| `CVs_Listos/` | Los CVs adaptados, en PDF, uno por vacante |
| `study_guides/` | Plan de estudio para las vacantes donde te faltan cosas |
| `master_profile.json` | Tu perfil maestro (lo que salió de tu CV + la entrevista) |
| `search_settings.json` | Lo que buscas (país, roles, años...) |
| `.env` | Tus llaves de IA. **No lo compartas** |
| `jobs.db` | Todas las vacantes evaluadas (para no repetirlas) |

## Cómo funciona el % de match
Es 100% técnico: cuántas de las tecnologías que pide la vacante tienes en tu perfil, menos un descuento si piden más
años de los que tienes. El tipo de rol es un filtro (si no es de los que elegiste, no aparece). 70%+ recibe CV;
40–69% aparece sin CV; menos de 40% no aparece. Solo se muestran vacantes donde te pueden contratar desde tu país
(o como contractor internacional sin pedir permiso de trabajo, si lo aceptaste).

## Si algo falla
- **"Python was not found"** (Windows): usa `py` en vez de `python`; si tampoco funciona, reinstala Python marcando
  *"Add python.exe to PATH"*.
- **"No encontré tu CV"**: el PDF tiene que estar en `Profiles/<tu nombre>/` y el nombre del comando tiene que ser
  igual al de la carpeta.
- **"Los proveedores fallaron" / sin cupo**: las llaves gratis tienen límite diario; vuelve a correr al otro día o
  agrega la segunda llave en tu `.env` (se abre con el bloc de notas).
- **No genera los PDF**: corre otra vez el tercer comando de la instalación (`… playwright install chromium`).
