import asyncio
import json
import os
import argparse
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from langchain_ollama import ChatOllama
from playwright.async_api import async_playwright
from database import get_job_by_url
import profile_paths

# --- 1. LLM PARA SÍNTESIS DINÁMICA ---
llm = ChatOllama(model="llama3.2", temperature=0.1)

async def map_form_and_solve(page, master_profile, cv_path=None):
    """Extrae el formulario actual, pregunta al LLM cómo llenarlo, y lo inyecta."""
    print("   [Bot] 1. Escaneando la estructura de la página web...")
    
    # ---------------------------------------------------------
    # FASE 0: BÚSQUEDA DE BOTONES "EDITAR" OCULTOS (Navegación RPA)
    # ---------------------------------------------------------
    inputs_count = await page.evaluate("document.querySelectorAll('input:not([type=\"hidden\"]):not([type=\"submit\"]):not([type=\"button\"]), textarea').length")
    
    if inputs_count == 0:
        print("   [Bot] No veo cajas de texto. Buscando botones de 'Editar' o 'Añadir' para abrir modales...")
        # Intentamos hacer clic en botones que típicamente abren formularios
        clicked = await page.evaluate('''() => {
            const btnKeywords = ['edit', 'editar', 'add', 'añadir', 'update'];
            const classKeywords = ['edit', 'pencil', 'icon-edit'];
            
            // Buscar botones, enlaces o spans clickeables
            const elements = Array.from(document.querySelectorAll('button, a, span, div'));
            
            for (let el of elements) {
                const text = (el.innerText || '').toLowerCase();
                const className = (el.className || '').toLowerCase();
                
                const matchesText = btnKeywords.some(kw => text.includes(kw) && text.length < 15);
                const matchesClass = classKeywords.some(kw => className.includes(kw));
                
                if ((matchesText || matchesClass) && el.offsetParent !== null) {
                    el.click();
                    return true; // Solo clickeamos el primero que encontremos
                }
            }
            return false;
        }''')
        
        if clicked:
            print("   [Bot] ¡Encontré un botón de edición y le hice clic! Esperando a que el formulario aparezca...")
            await asyncio.sleep(2) # Esperar a que la animación del modal termine
        else:
            print("   [Bot] No encontré ningún botón de edición obvio.")
    
    # ---------------------------------------------------------
    # FASE 1: EXTRACCIÓN DE CAMPOS
    # ---------------------------------------------------------
    # Extraemos todos los campos llenables (inputs, textareas, selects, cajas enriquecidas)
    inputs = await page.evaluate('''() => {
        const query = 'input:not([type="hidden"]):not([type="submit"]):not([type="button"]), textarea, select, [contenteditable="true"], [role="textbox"], [role="combobox"]';
        const elements = Array.from(document.querySelectorAll(query));
        
        return elements.map(el => {
            // Si el elemento no tiene ID ni Name (pasa mucho con el botón oculto de Upload CV), le inyectamos uno a la fuerza
            if (!el.id && !el.name && !el.getAttribute('name')) {
                el.id = 'agy_injected_' + Math.random().toString(36).substr(2, 5);
            }
            
            let label = "";
            if (el.id) {
                const labelEl = document.querySelector(`label[for="${el.id}"]`);
                if (labelEl) label = labelEl.innerText;
            }
            
            let options = [];
            if (el.tagName.toLowerCase() === 'select') {
                options = Array.from(el.options).map(opt => opt.text);
            }
            
            return {
                id: el.id,
                name: el.name || el.getAttribute('name'),
                type: el.type || el.getAttribute('type'),
                placeholder: el.placeholder || el.getAttribute('placeholder') || "",
                label: label,
                tag: el.tagName.toLowerCase(),
                is_editable: el.isContentEditable || false,
                options: options.length > 0 ? options : undefined
            };
        }); // Ya no filtramos, porque todos los elementos ahora tienen un ID inyectado garantizado
    }''')
    
    if not inputs:
        print("   [Bot] No encontré campos interactivos en esta página.")
        return

    print(f"   [Bot] Encontré {len(inputs)} campos. Consultando a Llama 3.2...")
    
    prompt = f"""
    Eres un RPA automatizador. Debes llenar este formulario web usando el perfil del candidato.
    
    PERFIL DEL CANDIDATO:
    {json.dumps(master_profile, ensure_ascii=False)}
    
    CAMPOS DEL FORMULARIO ENCONTRADOS:
    {json.dumps(inputs, ensure_ascii=False, indent=2)}
    
    INSTRUCCIONES:
    Para cada campo, genera el texto exacto que se debe escribir. Usa el perfil para inferir la mejor respuesta.
    Si es un archivo (type="file"), devuelve "upload_cv" como valor.
    Devuelve ÚNICAMENTE un JSON válido donde las llaves sean los "id" (o "name") del campo, y el valor sea el texto.
    No escribas NADA MÁS que el JSON.
    """
    
    response = await llm.ainvoke(prompt)
    
    raw_text = response.content.strip()
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:-3].strip()
    elif raw_text.startswith("```"):
        raw_text = raw_text[3:-3].strip()
        
    try:
        answers = json.loads(raw_text)
        print(f"   [Bot] Llama 3.2 generó respuestas para {len(answers)} campos. ¡Inyectando!")
        for selector_key, value in answers.items():
            matched_el = next((el for el in inputs if el['id'] == selector_key or el['name'] == selector_key), None)
            
            # Soporte para IDs dinámicos de campos ocultos (como CVs)
            selector = f"[id='{selector_key}']" if selector_key.startswith('agy_injected_') else f"#{selector_key}"
                
            try:
                if await page.locator(selector).count() == 0:
                    selector = f"[name='{selector_key}']"
                
                # REGLA 1: Chequeo de visibilidad (Excepción para inputs de archivos)
                is_file = matched_el and matched_el.get('type') == 'file'
                if not is_file and not await page.locator(selector).first.is_visible():
                    print(f"      -> [Saltado] {selector_key} (Oculto en Interfaz)")
                    continue

                if matched_el:
                    tag = matched_el.get('tag', '')
                    input_type = matched_el.get('type', '')
                    
                    if input_type == 'file':
                        # SUBIDA DE CV: Inyección directa saltando interfaz
                        if not cv_path or not os.path.exists(cv_path):
                            print(f"      -> [Saltado] {selector_key} (No hay CV generado para esta vacante. Corre tailor_agent.py primero)")
                            continue
                        await page.locator(selector).first.set_input_files(cv_path, timeout=5000)
                        print(f"      -> Archivo Subido: {selector_key} ({os.path.basename(cv_path)})")
                        
                    elif tag == 'select':
                        # DROPDOWNS NATIVOS
                        try:
                            await page.locator(selector).first.select_option(label=str(value), timeout=3000)
                            print(f"      -> Dropdown Nativado: {selector_key}")
                        except:
                            # FALLBACK REACT: Forzar valor vía JavaScript
                            await page.evaluate(f'''() => {{
                                const el = document.querySelector("{selector}");
                                if (el) {{
                                    el.value = "{value}";
                                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                }}
                            }}''')
                            print(f"      -> Dropdown Forzado (JS): {selector_key}")

                    elif input_type in ['checkbox', 'radio']:
                        # CASILLAS
                        is_checked = str(value).lower() in ['true', 'yes', '1', 'si', 'sí', 'on']
                        try:
                            if is_checked:
                                await page.locator(selector).first.check(timeout=3000)
                            else:
                                await page.locator(selector).first.uncheck(timeout=3000)
                            print(f"      -> Casilla {'Activada' if is_checked else 'Desactivada'}: {selector_key}")
                        except:
                            # FALLBACK REACT
                            await page.evaluate(f'''() => {{
                                const el = document.querySelector("{selector}");
                                if (el) {{
                                    el.checked = {'true' if is_checked else 'false'};
                                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                }}
                            }}''')
                            print(f"      -> Casilla Forzada (JS): {selector_key}")
                            
                    else:
                        # CAJAS DE TEXTO Y AUTOCOMPLETADO
                        try:
                            # Simulación Humana
                            await page.locator(selector).first.scroll_into_view_if_needed(timeout=2000)
                            await page.locator(selector).first.click(timeout=2000) 
                            await page.locator(selector).first.fill("", timeout=2000)
                            await page.locator(selector).first.press_sequentially(str(value), delay=30)
                            await page.locator(selector).first.press("Enter") # Forzar cierre de autocompletados
                            await page.locator(selector).first.press("Tab") # Mover foco
                            print(f"      -> Texto Humano: {selector_key}")
                        except:
                            # FALLBACK REACT: Hack de Propiedades de React 16+
                            await page.evaluate(f'''() => {{
                                const el = document.querySelector("{selector}");
                                if (el) {{
                                    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                                    nativeInputValueSetter.call(el, "{value}");
                                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                }}
                            }}''')
                            print(f"      -> Texto Forzado (JS React-Hack): {selector_key}")
                else:
                    # FALLBACK GENÉRICO
                    await page.locator(selector).first.fill(str(value), force=True, timeout=3000)
                    await page.locator(selector).first.press("Enter")
                    print(f"      -> Texto Fijado (Fallback): {selector_key}")
                    
                await asyncio.sleep(0.5)
            except Exception as e:
                error_msg = str(e).splitlines()[0] if str(e).splitlines() else str(e)
                print(f"      -> [Error Severo] {selector_key} | {error_msg}")
                
    except json.JSONDecodeError:
        print("   [Error] El LLM no devolvió un JSON válido. Respuesta cruda:")
        print(raw_text)

async def run_applicator(target_url):
    print("====================================================")
    print(" Agente 4: MODO DE LLENADO AUTÓNOMO (RPA) ")
    print("====================================================\n")
    
    state_file = "auth_state.json"
    if not os.path.exists(state_file):
        print("[FATAL ERROR] No tienes auth_state.json guardado.")
        return

    with open(profile_paths.resolve("master_profile.json"), "r", encoding="utf-8") as f:
        master_profile = json.load(f)

    job = get_job_by_url(target_url)
    cv_path = None
    if job and job.get("cv_path"):
        cv_path = os.path.abspath(job["cv_path"])
        print(f"[+] CV encontrado para esta vacante: {cv_path}")
    else:
        print("[!] ADVERTENCIA: No encontré un CV generado (tailor_agent.py) para esta URL en jobs.db. Se omitirá la subida de archivo.")

    async with async_playwright() as p:
        print("[+] Levantando navegador con tus cookies inyectadas...")
        browser = await p.chromium.launch(
            headless=False, 
            channel="msedge",
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(storage_state=state_file)
        page = await context.new_page()

        print(f"[+] Navegando autónomamente a: {target_url}")
        # Evitamos 'networkidle' porque Workana tiene websockets y trackers que nunca se quedan quietos
        await page.goto(target_url, wait_until="domcontentloaded")
        await asyncio.sleep(3) # Pausa manual para asegurar que reaccione (React, JS)
        
        print("[+] Resolviendo formulario...")
        await map_form_and_solve(page, master_profile, cv_path)
        
        input("\n[PAUSA FINAL] Revisa cómo lo llenó el bot. Presiona ENTER para cerrar el navegador.")
        await browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agente 4 - Llenador de Formularios Autónomo")
    parser.add_argument("--url", type=str, required=True, help="URL exacta del formulario a llenar")
    args = parser.parse_args()
    
    asyncio.run(run_applicator(args.url))
