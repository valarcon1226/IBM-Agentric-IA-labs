# Plan — Agente Aplicador (Agente 4)

_Creado: 2026-09-30. Objetivo: que jobHunter postule solo a las vacantes con CV (70%+): abre la oferta, sigue la redirección
a la página de la empresa, llena el formulario, sube el CV, responde las preguntas con la información real de Valentina y
envía. Todo gratis y en el homelab._

---

## 1. Qué hay hoy

| Pieza | Estado | Problema |
|---|---|---|
| `applicator_agent.py` | Prototipo manual: `--url` de UNA página, escanea inputs, le pide a un LLM un JSON campo→valor y lo llena | Usa `llama3.2` (el homelab tiene `qwen3:4b`); navegador visible con Edge (solo Windows); no sigue la redirección de LinkedIn/Indeed a la empresa; no maneja formularios de varios pasos; **nunca envía**; no guarda nada en la DB; manda el perfil completo al LLM en cada página; la heurística de "clic en Editar" puede tocar cualquier botón |
| `login_setup.py` | Guarda cookies de ~10 plataformas en `auth_state.json` | Pensado para freelance; sesiones que caducan; no sirve en el homelab (pide ENTER a mano) |
| `jobs.db` | Vacantes con `url`, `cv_path`, `match_percentage`, `gap_analysis`, `applied_at` | No guarda el **link directo para postular** (`job_url_direct` de JobSpy) ni en qué ATS está |
| Tailor | CV PDF por vacante 70%+ en `CVs_Listos/` | Listo para subir |
| Dashboard | Botón "Aplicada" por vacante | No hay cola de revisión de respuestas |
| Playwright | Ya instalado en la imagen Docker (lo usa el Tailor para el PDF) | — |

## 2. Decisiones de diseño (léelas antes de construir)

1. **No automatizar LinkedIn ni Indeed.** Sus términos prohíben bots; automatizar Easy Apply es la forma más rápida de perder
   la cuenta de LinkedIn, que además es tu canal principal. El agente usa LinkedIn/Indeed solo para **encontrar el link de la
   empresa** y postula ahí. Las ofertas que solo tienen Easy Apply quedan en una lista "postular a mano" (2 min cada una).
2. **ATS primero, genérico después.** La mayoría de las empresas remotas usan unos pocos sistemas de postulación con
   formularios públicos, sin login y con estructura fija: **Greenhouse, Lever, Ashby** (luego Workable, SmartRecruiters,
   BambooHR). Para esos se escribe un manejador determinístico (sin LLM para los campos estándar). El LLM solo responde las
   preguntas abiertas. Workday pide crear cuenta por empresa → fase posterior.
3. **Nunca inventar.** El agente responde "como si fueras tú", pero solo con datos que tú diste. Pregunta que no sabe
   responder con certeza → se pausa, te la pregunta en el dashboard y guarda tu respuesta para la próxima vez (aprende).
4. **CAPTCHA = humano.** No se evaden CAPTCHAs; la vacante pasa a "necesita tu clic" en el dashboard.
5. **Dos modos.** `revisar` (default al inicio): llena todo, saca captura y espera tu OK en el dashboard. `auto`: envía solo
   cuando el ATS está soportado y todas las respuestas salieron del banco de respuestas o del perfil. Se pasa a `auto` por ATS
   cuando `revisar` lleve ~20 envíos sin correcciones.
6. **Cupo.** Campos estándar = 0 llamadas. Preguntas cortas = modelo local. Solo textos largos ("¿por qué te interesa?",
   carta) usan la nube: ~1–2 llamadas por postulación → con tope de 25 postulaciones/día son ~50 llamadas, dentro del cupo.
7. **Ritmo humano.** Máximo 25 postulaciones/día, espaciadas (5–15 min), solo vacantes 80%+ al principio.

## 3. Qué falta y cómo hacerlo

### Fase 0 — Tu parte (antes de construir) · ~1 h
- **Banco de respuestas** `Profiles/answers.yaml` (fuera de git, como el perfil): nombre legal, email, teléfono, ciudad/país,
  LinkedIn, GitHub, portafolio, link del CV en Drive; autorización de trabajo por país (US/UE/LATAM), ¿necesitas visa?,
  expectativa salarial (USD/mes y anual, rango), preaviso/disponibilidad, zona horaria y horas de solapamiento, ¿relocalizarte?,
  inglés (nivel), años por skill (Python, Playwright, QA, LLMs…), cómo te enteraste ("LinkedIn"), preferencias EEO
  (género/raza/veteranía/discapacidad → "prefiero no decir" si quieres), y 3–4 respuestas modelo tuyas: por qué te
  interesa este tipo de rol, tu mayor logro, por qué dejas/buscas trabajo.
- Un email para postulaciones (puede ser el tuyo) y, si quieres la confirmación automática, acceso de lectura a ese Gmail.

### Fase 1 — Encontrar dónde se postula · ~1 día
- En `job_scraper.py` guardar `job_url_direct` de JobSpy (LinkedIn con `linkedin_fetch_description=True` e Indeed lo traen
  cuando la oferta redirige a la empresa) en una columna nueva `apply_url` (+ migración en `database.init_db`).
- `apply_resolver.py`: si no hay `apply_url`, abrir la oferta sin login y leer el botón "Apply on company site"; si solo hay
  Easy Apply → `apply_mode = 'manual'`.
- Clasificar el ATS por dominio (`boards.greenhouse.io`, `jobs.lever.co`, `jobs.ashbyhq.com`, `apply.workable.com`,
  `jobs.smartrecruiters.com`, `*.myworkdayjobs.com`…) → columna `ats`.
- Script de conteo: cuántas vacantes 70%+ caen en cada ATS → decide el orden de la Fase 2 con datos.
- **Verificar**: ≥60% de las vacantes 70%+ con `apply_url` resuelto.

### Fase 2 — Manejadores por ATS · ~1 día por ATS
- `applicator/ats/greenhouse.py`, `lever.py`, `ashby.py`: cada uno sabe dónde están nombre, email, teléfono, CV, LinkedIn,
  carta, preguntas personalizadas y el botón de enviar. Playwright **headless** con Chromium (no Edge), en el contenedor.
- Leer las preguntas personalizadas como lista `{label, tipo, opciones, obligatoria}` y pasarlas al motor de respuestas.
- Captura de pantalla antes de enviar y después (confirmación) → `applications/<job_id>/`.
- **Verificar**: en modo `revisar`, 5 vacantes reales por ATS llenas al 100% sin enviar; revisar capturas.

### Fase 3 — Motor de respuestas · ~1–2 días
Por cada pregunta, en orden, y se queda con la primera que responde:
1. **Banco de respuestas** (coincidencia de etiqueta normalizada: "Are you legally authorized to work in…",
   "Desired salary"…). Respuesta exacta, sin LLM.
2. **Perfil** (`master_profile.json`): años, skills, estudios, experiencia.
3. **Opción de lista** (select/radio): elegir la opción que corresponde al dato 1–2; si ninguna encaja → paso 5.
4. **Texto abierto** ("Why are you interested…"): LLM de la nube con tu perfil + la vacante + tus respuestas modelo del banco
   como guía de estilo (sin frases de IA, como el párrafo de Agile Fuel). Límite de palabras del campo.
5. **No sabe** → la vacante pasa a `Necesita respuesta`, la pregunta aparece en el dashboard; cuando respondes se guarda en
   el banco y la vacante vuelve a la cola.
- Cada respuesta guarda su fuente (banco/perfil/LLM/tú) en `application_answers` (tabla nueva) para auditar.
- **Verificar**: test sin navegador con 30 preguntas reales sacadas de la Fase 2: 0 respuestas inventadas en datos duros.

### Fase 4 — Servicio y estados · ~1 día
- `applicator_agent.py` reescrito como servicio `applicator` en `docker-compose.yml` (loop como el tailor): toma vacantes
  `CV Generado`, 80%+ (configurable `APPLY_MIN_MATCH`), `ats` soportado, sin `applied_at`; tope `APPLY_DAILY_CAP=25`.
- Estados nuevos: `Lista para enviar` (modo revisar) → `Aplicada` (guarda `applied_at` + capturas) · `Necesita respuesta` ·
  `Postular a mano` (Easy Apply / ATS no soportado / CAPTCHA) · `Error al aplicar` (con el motivo, reintenta 1 vez).
- Se borra la heurística de "clic en Editar" y el `input()` del prototipo.

### Fase 5 — Dashboard · ~1 día
- Pestaña **Aplicador**: cola "Lista para enviar" con captura + respuestas (editables) + botón **Enviar**; lista
  "Necesita respuesta" con un campo por pregunta; lista "Postular a mano" con link directo y CV; historial de enviadas.
- Filtro por estado nuevo en la pestaña 9-5.

### Siguiente agente — Seguimiento por correo (Agente 5)
- Lee el Gmail de postulaciones (API de Gmail, solo lectura, gratis), empareja cada email con su vacante (empresa/ATS),
  clasifica con el modelo local: confirmación · rechazo · entrevista/siguiente paso · prueba técnica · pide información.
- Actualiza el estado en jobs.db y el dashboard, y te avisa de lo que requiere acción (entrevista, prueba, pregunta).
- Recordatorio de seguimiento si no hay respuesta en N días. Se diseña cuando el aplicador esté enviando.

### Fase 6 — Después (opcional)
- Más ATS (Workable, SmartRecruiters, BambooHR, Teamtailor).
- Workday: crear cuenta por empresa (necesita guardar credenciales cifradas) — solo si el conteo de la Fase 1 lo justifica.
- Lectura de Gmail para marcar "confirmada" cuando llega el email del ATS.
- Freelance (Workana/Freelancer): redactor de propuestas con envío manual — es otra lógica (propuesta, precio, plazo).

## 4. Riesgos

| Riesgo | Mitigación |
|---|---|
| Respuesta falsa en una postulación | Banco de respuestas + "no sabe → te pregunta"; modo revisar al inicio; auditoría por respuesta |
| Bloqueo de cuentas | No se automatiza LinkedIn/Indeed; ATS públicos sin login; ritmo humano y tope diario |
| Cambios en el HTML de un ATS | Un manejador por ATS con test en modo revisar; si falla → `Error al aplicar`, no envía a medias |
| GPU saturada | Campos estándar sin LLM; textos largos en la nube (1–2 llamadas); el aplicador corre en horario sin scout |
| CAPTCHA | Pasa a humano; nunca se evade |

## 5. Orden y tiempos
Fase 0 (tú) → 1 → 2 (Greenhouse, luego el ATS más frecuente según el conteo) → 3 → 4 → 5. Primer envío real en modo
revisar: ~5–6 días de trabajo. Por el tamaño, las fases 1–5 se delegan a Codex con este archivo como guía (regla ponytail),
y se revisa cada fase antes de desplegar.
