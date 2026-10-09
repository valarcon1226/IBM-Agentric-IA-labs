import pytest
import datetime
from playwright.sync_api import Page, expect

def test_keyboard_navigation(page: Page):
    page.goto("http://localhost:8004/widget/demo/index.html")
    
    btn = page.get_by_role("button", name="Abrir chat")
    btn.focus()
    expect(btn).to_be_focused()
    
    btn.press("Enter")
    
    input = page.get_by_role("textbox", name="Mensaje")
    expect(input).to_be_focused()
    
    input.fill("test")
    input.press("Enter")
    
    expect(page.locator("text=Escribiendo...")).to_be_hidden(timeout=10000)
    
    input.press("Escape")
    expect(btn).to_be_focused()

def test_ask_menu(page: Page):
    page.goto("http://localhost:8004/widget/demo/index.html")
    btn = page.get_by_role("button", name="Abrir chat")
    btn.click()
    
    input = page.get_by_role("textbox", name="Mensaje")
    input.fill('{"tool": "get_menu", "arguments": {}}')
    input.press("Enter")
    
    # Just asserting text nodes since there's no class
    expect(page.locator("text=Escribiendo...")).to_be_hidden(timeout=10000)
    expect(page.locator("text=Ajiaco").last).to_be_visible(timeout=10000)

def test_make_reservation(page: Page):
    page.goto("http://localhost:8004/widget/demo/index.html")
    btn = page.get_by_role("button", name="Abrir chat")
    btn.click()
    
    input = page.get_by_role("textbox", name="Mensaje")
    
    t = datetime.date.today() + datetime.timedelta(days=1)
    if t.weekday() == 0:
        t += datetime.timedelta(days=1)
    res_date = t.isoformat()
    
    script = f'{{"tool": "create_reservation", "arguments": {{"date": "{res_date}", "time": "19:00", "party_size": 2}}}}'
    input.fill(script)
    input.press("Enter")
    
    expect(page.locator("text=Escribiendo...")).to_be_hidden(timeout=10000)
    expect(page.locator("text=reservation").last).to_be_visible(timeout=10000)
    
    assert len(pytest.fake_db.reservations) > 0
    res = list(pytest.fake_db.reservations.values())[-1]
    assert res.party_size == 2

def test_admin_panel(page: Page):
    page.goto("http://localhost:8004/admin")
    
    page.set_input_files('input[name="file"]', {
        'name': 'test_oferta.md',
        'mimeType': 'text/markdown',
        'buffer': b'# Oferta Especial\nHoy tenemos pizza gratis.'
    })
    
    messages = []
    page.on("dialog", lambda dialog: (messages.append(dialog.message), dialog.accept()))
    
    page.click('button[type="submit"]')
    page.wait_for_timeout(1000)
    assert "Falta el token" in "".join(messages) or "401" in "".join(messages)
    
    page.fill('input[name="token"]', "test_dev_api_key")
    messages.clear()
    page.click('button[type="submit"]')
    page.wait_for_timeout(1000)
    
    import os
    knowledge_dir = os.path.join(os.path.dirname(__file__), "..", "..", "13-whatsapp-restaurant-assistant", "knowledge")
    test_file = os.path.join(knowledge_dir, "test_oferta.md")
    assert os.path.exists(test_file)
    os.remove(test_file)
