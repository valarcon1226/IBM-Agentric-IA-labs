# jobHunter: encuentra vacantes y genera tu CV a la medida

Busca vacantes remotas en LinkedIn según tu perfil, les pone un % de match técnico, genera un CV adaptado para las
que superan 70% y te arma un reporte con todo (link a la oferta, tu CV y lo que te falta estudiar).
Gratis: usa tus propias llaves de IA (sin tarjeta). Por ahora es solo para empleos 9-5 en roles técnicos.

## Instalación (una sola vez)

1. Instala **Python 3.11 o más nuevo** (python.org). En Windows marca *"Add Python to PATH"*.
2. Descarga este proyecto y abre una terminal dentro de la carpeta `jobHunter`.
3. Instala las dependencias:
   ```
   py -m pip install -r requirements.txt
   py -m playwright install chromium
   ```
   Si el primer comando falla por `numpy`, corre `py -m pip install --no-deps python-jobspy` y repítelo.
4. *(Opcional)* Si tu PC tiene buena tarjeta de video, instala [Ollama](https://ollama.com) y corre
   `ollama pull qwen3:4b`: lo pesado corre en tu PC y te rinde más el cupo gratis de las llaves.

## Uso

1. Crea una carpeta con tu nombre dentro de `Profiles/` y pon tu **hoja de vida en PDF**:
   `Profiles/Ana Gomez/Hoja de vida Ana Gomez.pdf`
2. Corre:
   ```
   py main.py "Ana Gomez"
   ```
3. La primera vez:
   - Te pide **tus llaves de IA** (gratis): Gemini en https://aistudio.google.com/apikey y Groq en
     https://console.groq.com/keys. Con una basta; con dos rinde más. Se guardan en tu carpeta, en `.env`.
   - **Lee tu CV y te entrevista** para completar lo que falta (métricas, salario, modalidad...). Responde y deja una
     línea vacía para enviar; escribe `salir` para terminar.
   - Te pregunta **qué buscas**: país, tipos de rol, años de experiencia y si aceptas trabajar como contractor para
     empresas de afuera.
4. Busca vacantes (máx. ~30 min), genera hasta 10 CVs y **abre el reporte** en tu navegador.

Las siguientes veces solo te pregunta si hubo cambios en tu CV o en lo que buscas; si no, va directo a buscar.
`py main.py "Ana Gomez" --reporte` solo vuelve a abrir el reporte.

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
- **"Los proveedores fallaron" / sin cupo**: las llaves gratis tienen límite diario; vuelve a correr al otro día o
  agrega la segunda llave en tu `.env`.
- **No genera los PDF**: corre `py -m playwright install chromium`.
- **No encuentra tu CV**: tiene que estar en PDF dentro de `Profiles/<tu nombre>/`.
