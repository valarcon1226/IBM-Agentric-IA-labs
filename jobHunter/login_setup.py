import asyncio
import os
from playwright.async_api import async_playwright

async def main():
    state_file = "auth_state.json"
    
    print("====================================================")
    print(" MEGA MODO DE CAPTURA DE SESIONES FREELANCE ")
    print("====================================================")
    print("Se abrira tu navegador con 10 pestañas en simultaneo.")
    print("Logueate con paciencia en TODAS. Cierra los popups.")
    print("Al terminar, vuelve a esta consola y presiona ENTER.")
    
    urls = [
        "https://www.upwork.com/ab/account-security/login",
        "https://www.workana.com/login",
        "https://www.freelancer.com/login",
        "https://www.fiverr.com/login",
        "https://www.peopleperhour.com/login",
        "https://www.guru.com/login.aspx",
        "https://arc.dev/login",
        "https://app.gun.io/login",
        "https://www.toptal.com/users/login",
        "https://www.malt.com/user/login"
    ]
    
    async with async_playwright() as p:
        # Modo Anti-Bot encendido y usando Edge
        browser = await p.chromium.launch(
            headless=False, 
            channel="msedge",
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        # Cargar LinkedIn que ya tenías guardado
        if os.path.exists(state_file):
            print("[+] Cargando tu LinkedIn previamente guardado...")
            context = await browser.new_context(storage_state=state_file)
        else:
            context = await browser.new_context()
            
        # Abrir todas las pestañas de golpe
        print("[+] Lanzando las 10 plataformas freelance...")
        for url in urls:
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            # Esperamos 1 segundo entre pestañas para no colapsar la RAM de golpe
            await asyncio.sleep(1)
            
        input("\n[PAUSA] Revisa tu navegador. Logueate en todas y presiona ENTER aqui al terminar...")
        
        # Guardar la súper cookie
        await context.storage_state(path=state_file)
        print("\n¡Exito absoluto! Todas tus sesiones consolidadas en 'auth_state.json'.")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
