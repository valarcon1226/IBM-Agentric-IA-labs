"""Generates 6 synthetic PDF invoices and raw text fixtures for testing."""

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def draw_watermark(c: canvas.Canvas, width: float, height: float):
    c.saveState()
    c.setFont("Helvetica-Bold", 10)
    c.setFillColorRGB(0.7, 0.7, 0.7)
    c.drawCentredString(
        width / 2.0, height - 30, "DOCUMENTO FICTICIO PARA PRUEBAS DE AUTOMATIZACION"
    )
    c.drawCentredString(width / 2.0, 30, "DOCUMENTO FICTICIO - NO TIENE VALIDEZ FISCAL NI LEGAL")
    c.restoreState()


def generar_factura_1_limpia(output_path: Path):
    """Factura limpia estándar colombiana, matemáticamente consistente."""
    c = canvas.Canvas(str(output_path), pagesize=letter)
    width, height = letter

    draw_watermark(c, width, height)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 70, "SOLUCIONES ANDINAS S.A.S.")

    c.setFont("Helvetica", 10)
    c.drawString(50, height - 90, "NIT: 900.123.456-8")
    c.drawString(50, height - 105, "Dirección: Calle 100 # 15-20, Bogotá, Colombia")
    c.drawString(
        50, height - 120, "Teléfono: +57 601 555-1234 | Correo: contacto@solucionesandinas.ficticio"
    )

    c.setFont("Helvetica-Bold", 11)
    c.drawString(350, height - 70, "FACTURA ELECTRONICA")
    c.setFont("Helvetica", 10)
    c.drawString(350, height - 85, "Factura No: FEV-1001")
    c.drawString(350, height - 100, "Fecha de Emisión: 2026-10-01")
    c.drawString(350, height - 115, "Fecha de Vencimiento: 2026-10-31")

    # Separator
    c.setLineWidth(1)
    c.setStrokeColorRGB(0.8, 0.8, 0.8)
    c.line(50, height - 135, width - 50, height - 135)

    # Recipient
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, height - 155, "DATOS DEL CLIENTE:")
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 170, "Cliente: COMERCIALIZADORA DEL CARIBE S.A.")
    c.drawString(50, height - 185, "NIT: 800.987.654-3")
    c.drawString(50, height - 200, "Dirección: Carrera 50 # 70-10, Barranquilla, Colombia")

    # Table Header
    y = height - 240
    c.setFillColorRGB(0.95, 0.95, 0.95)
    c.rect(50, y - 5, width - 100, 20, fill=True, stroke=False)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(60, y, "Descripción")
    c.drawString(280, y, "Cantidad")
    c.drawString(370, y, "Precio Unitario")
    c.drawString(480, y, "Total")

    # Items
    items = [
        ("Licencias de Software Cloud", "10", "100000", "1000000"),
        ("Soporte Tecnico Mensual", "1", "500000", "500000"),
    ]

    c.setFont("Helvetica", 10)
    for desc, qty, price, total in items:
        y -= 25
        c.drawString(60, y, desc)
        c.drawString(290, y, qty)
        c.drawString(370, y, f"$ {int(price):,}")
        c.drawString(480, y, f"$ {int(total):,}")

    # Totals
    y -= 50
    c.setLineWidth(1)
    c.line(350, y + 15, width - 50, y + 15)

    c.setFont("Helvetica-Bold", 10)
    c.drawString(350, y, "Subtotal: $ 1,500,000")

    y -= 20
    c.drawString(350, y, "IVA (19%): $ 285,000")

    y -= 25
    c.setFont("Helvetica-Bold", 12)
    c.drawString(350, y, "Total a Pagar: $ 1,785,000")

    c.showPage()
    c.save()


def generar_factura_2_ruido(output_path: Path):
    """Factura con ligera inclinación y grano/ruido visual simulando escaneo."""
    c = canvas.Canvas(str(output_path), pagesize=letter)
    width, height = letter

    # Apply minor rotation and noise elements
    c.saveState()
    c.translate(10, -5)
    c.rotate(-0.8)

    draw_watermark(c, width, height)

    c.setFont("Courier-Bold", 15)
    c.drawString(50, height - 70, "LOGISTICA Y ENVIOS DEL PACIFICO S.A.S.")

    c.setFont("Courier", 10)
    c.drawString(50, height - 90, "NIT: 900.123.456-8")
    c.drawString(50, height - 105, "Dirección: Av Central # 45-80, Cali, Colombia")

    c.setFont("Courier-Bold", 11)
    c.drawString(350, height - 70, "FACTURA DE VENTA")
    c.setFont("Courier", 10)
    c.drawString(350, height - 85, "Factura No: FEV-2002")
    c.drawString(350, height - 100, "Fecha: 2026-10-02")

    c.drawString(50, height - 140, "Cliente: DISTRIBUCIONES OCCIDENTE LTDA")
    c.drawString(50, height - 155, "NIT: 890.111.222-3")

    y = height - 200
    c.drawString(50, y, "Fletes de Transporte de Carga  5  100000  500000")
    c.drawString(50, y - 25, "Servicio de Embalaje Especial  1  200000  200000")

    y -= 80
    c.drawString(350, y, "Subtotal: $ 700,000")
    c.drawString(350, y - 20, "IVA (19%): $ 133,000")
    c.drawString(350, y - 45, "Total: $ 833,000")

    # Add scattered faint dots to simulate scanner noise
    c.setFillColorRGB(0.75, 0.75, 0.75)
    for x_dot, y_dot in [(40, 100), (500, 200), (120, 600), (300, 450), (450, 700), (80, 400)]:
        c.circle(x_dot, y_dot, 1.2, fill=True, stroke=False)

    c.restoreState()
    c.showPage()
    c.save()


def generar_factura_3_multipage(output_path: Path):
    """Factura de 2 páginas con múltiples ítems y subtotales."""
    c = canvas.Canvas(str(output_path), pagesize=letter)
    width, height = letter

    # --- Page 1 ---
    draw_watermark(c, width, height)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 70, "DISTRIBUIDORA NACIONAL LOGISTICA S.A.S.")
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 90, "NIT: 901.234.567-7")
    c.drawString(50, height - 105, "Factura No: FEV-3003")
    c.drawString(50, height - 120, "Fecha de Emisión: 2026-10-03")
    c.drawString(50, height - 135, "Cliente: ALMACENES UNIDOS S.A.")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, height - 170, "Página 1 de 2 - Detalle de Ítems:")

    y = height - 200
    items_p1 = [
        ("Servidor Blade Enterprise Gen10", "2", "3000000", "6000000"),
        ("Modulo de Memoria RAM 64GB", "8", "250000", "2000000"),
        ("Disco Estado Solido 2TB NVMe", "4", "500000", "2000000"),
    ]
    c.setFont("Helvetica", 10)
    for desc, qty, price, total in items_p1:
        c.drawString(50, y, f"{desc} | {qty} | {price} | {total}")
        y -= 25

    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(width / 2.0, 50, "Continúa en la página 2...")
    c.showPage()

    # --- Page 2 ---
    draw_watermark(c, width, height)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 70, "DISTRIBUIDORA NACIONAL LOGISTICA S.A.S. - Página 2")
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 90, "Factura No: FEV-3003")

    y = height - 130
    items_p2 = [
        ("Switch Gestionable 24 Puertos", "1", "1500000", "1500000"),
        ("Cableado Estructurado Cat6A", "1", "500000", "500000"),
    ]
    for desc, qty, price, total in items_p2:
        c.drawString(50, y, f"{desc} | {qty} | {price} | {total}")
        y -= 25

    y -= 50
    c.setFont("Helvetica-Bold", 11)
    c.drawString(350, y, "Subtotal: $ 12,000,000")
    c.drawString(350, y - 20, "IVA (19%): $ 2,280,000")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(350, y - 45, "Total: $ 14,280,000")

    c.showPage()
    c.save()


def generar_factura_4_descuadre(output_path: Path):
    """Factura con errores matemáticos (IVA y Total descuadrados)."""
    c = canvas.Canvas(str(output_path), pagesize=letter)
    width, height = letter

    draw_watermark(c, width, height)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 70, "SERVICIOS INDUSTRIALES DEL VALLE S.A.S.")
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 90, "NIT: 900.123.456-8")
    c.drawString(50, height - 105, "Factura No: FEV-4004")
    c.drawString(50, height - 120, "Fecha: 2026-10-04")
    c.drawString(50, height - 135, "Cliente: MANUFACTURAS DEL NORTE")

    y = height - 180
    c.drawString(50, y, "Mantenimiento Preventivo Maquinaria  1  1000000  1000000")

    y -= 50
    # Calculations are intentionally wrong!
    # Subtotal 1,000,000; IVA 19% says 50,000 (should be 190,000);
    # Total says 2,000,000 (should be 1,190,000)
    c.drawString(350, y, "Subtotal: $ 1,000,000")
    c.drawString(350, y - 20, "IVA (19%): $ 50,000")
    c.drawString(350, y - 45, "Total: $ 2,000,000")

    c.showPage()
    c.save()


def generar_factura_5_sin_nit(output_path: Path):
    """Factura que carece de NIT/VAT de emisor."""
    c = canvas.Canvas(str(output_path), pagesize=letter)
    width, height = letter

    draw_watermark(c, width, height)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 70, "CONSULTORES INDEPENDIENTES ASOCIADOS")
    c.setFont("Helvetica", 10)
    # Notice: NO NIT provided!
    c.drawString(50, height - 90, "Dirección: Carrera 7 # 32-16, Bogotá, Colombia")
    c.drawString(50, height - 105, "Factura No: FEV-5005")
    c.drawString(50, height - 120, "Fecha: 2026-10-05")
    c.drawString(50, height - 135, "Cliente: ASESORIAS INTEGRALES LTDA")

    y = height - 180
    c.drawString(50, y, "Asesoria Financiera y Tributaria  1  800000  800000")

    y -= 50
    c.drawString(350, y, "Subtotal: $ 800,000")
    c.drawString(350, y - 20, "IVA (19%): $ 152,000")
    c.drawString(350, y - 45, "Total: $ 952,000")

    c.showPage()
    c.save()


def generar_factura_6_ingles(output_path: Path):
    """Factura internacional en inglés con formato USD y VAT ID."""
    c = canvas.Canvas(str(output_path), pagesize=letter)
    width, height = letter

    draw_watermark(c, width, height)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 70, "GLOBAL CLOUD SOLUTIONS INC")
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 90, "VAT ID: US-987654321")
    c.drawString(50, height - 105, "Address: 500 Tech Blvd, Austin, TX, USA")

    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(width - 50, height - 70, "INVOICE")
    c.setFont("Helvetica", 10)
    c.drawRightString(width - 50, height - 90, "Invoice #: INV-2026-6006")
    c.drawRightString(width - 50, height - 105, "Date: 2026-10-06")

    c.drawString(50, height - 140, "Bill To: ANDES TECH LABS SAS")
    c.drawString(50, height - 155, "Customer ID: CUST-7788")

    y = height - 200
    c.drawString(50, y, "Dedicated Cloud Server Hosting  1  500.00  500.00")
    c.drawString(50, y - 25, "Database Backup & Replication  1  200.00  200.00")

    y -= 75
    c.drawString(350, y, "Subtotal: $ 700.00")
    c.drawString(350, y - 20, "Tax (10%): $ 70.00")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(350, y - 45, "Grand Total: $ 770.00")

    c.showPage()
    c.save()


def generar_text_fixtures():
    """Generates pre-extracted raw text fixtures for lightning-fast unit tests."""
    fixtures = {
        "raw_text_1_limpia.txt": (
            "DOCUMENTO FICTICIO PARA PRUEBAS DE AUTOMATIZACION\n"
            "SOLUCIONES ANDINAS S.A.S.\n"
            "NIT: 900.123.456-8\n"
            "Dirección: Calle 100 # 15-20, Bogotá, Colombia\n"
            "FACTURA ELECTRONICA DE VENTA\n"
            "Factura No: FEV-1001\n"
            "Fecha de Emisión: 2026-10-01\n"
            "Fecha de Vencimiento: 2026-10-31\n"
            "DATOS DEL CLIENTE:\n"
            "Cliente: COMERCIALIZADORA DEL CARIBE S.A.\n"
            "NIT: 800.987.654-3\n"
            "Licencias de Software Cloud  10  100000  1000000\n"
            "Soporte Tecnico Mensual  1  500000  500000\n"
            "Subtotal: $ 1,500,000\n"
            "IVA (19%): $ 285,000\n"
            "Total a Pagar: $ 1,785,000\n"
        ),
        "raw_text_2_ruido.txt": (
            "DOCUMENTO FICTICIO PARA PRUEBAS DE AUTOMATIZACION\n"
            "LOGISTICA Y ENVIOS DEL PACIFICO S.A.S.\n"
            "NIT: 900.123.456-8\n"
            "FACTURA DE VENTA\n"
            "Factura No: FEV-2002\n"
            "Fecha: 2026-10-02\n"
            "Cliente: DISTRIBUCIONES OCCIDENTE LTDA\n"
            "NIT: 890.111.222-3\n"
            "Fletes de Transporte de Carga  5  100000  500000\n"
            "Servicio de Embalaje Especial  1  200000  200000\n"
            "Subtotal: $ 700,000\n"
            "IVA (19%): $ 133,000\n"
            "Total: $ 833,000\n"
        ),
        "raw_text_3_multipage.txt": (
            "DOCUMENTO FICTICIO PARA PRUEBAS DE AUTOMATIZACION\n"
            "DISTRIBUIDORA NACIONAL LOGISTICA S.A.S.\n"
            "NIT: 901.234.567-7\n"
            "Factura No: FEV-3003\n"
            "Fecha de Emisión: 2026-10-03\n"
            "Cliente: ALMACENES UNIDOS S.A.\n"
            "Servidor Blade Enterprise Gen10 | 2 | 3000000 | 6000000\n"
            "Modulo de Memoria RAM 64GB | 8 | 250000 | 2000000\n"
            "Disco Estado Solido 2TB NVMe | 4 | 500000 | 2000000\n"
            "--- PAGE BREAK ---\n"
            "Switch Gestionable 24 Puertos | 1 | 1500000 | 1500000\n"
            "Cableado Estructurado Cat6A | 1 | 500000 | 500000\n"
            "Subtotal: $ 12,000,000\n"
            "IVA (19%): $ 2,280,000\n"
            "Total: $ 14,280,000\n"
        ),
        "raw_text_4_descuadre.txt": (
            "DOCUMENTO FICTICIO PARA PRUEBAS DE AUTOMATIZACION\n"
            "SERVICIOS INDUSTRIALES DEL VALLE S.A.S.\n"
            "NIT: 900.123.456-8\n"
            "Factura No: FEV-4004\n"
            "Fecha: 2026-10-04\n"
            "Cliente: MANUFACTURAS DEL NORTE\n"
            "Mantenimiento Preventivo Maquinaria  1  1000000  1000000\n"
            "Subtotal: $ 1,000,000\n"
            "IVA (19%): $ 50,000\n"
            "Total: $ 2,000,000\n"
        ),
        "raw_text_5_sin_nit.txt": (
            "DOCUMENTO FICTICIO PARA PRUEBAS DE AUTOMATIZACION\n"
            "CONSULTORES INDEPENDIENTES ASOCIADOS\n"
            "Dirección: Carrera 7 # 32-16, Bogotá, Colombia\n"
            "Factura No: FEV-5005\n"
            "Fecha: 2026-10-05\n"
            "Cliente: ASESORIAS INTEGRALES LTDA\n"
            "Asesoria Financiera y Tributaria  1  800000  800000\n"
            "Subtotal: $ 800,000\n"
            "IVA (19%): $ 152,000\n"
            "Total: $ 952,000\n"
        ),
        "raw_text_6_ingles.txt": (
            "DOCUMENTO FICTICIO PARA PRUEBAS DE AUTOMATIZACION\n"
            "GLOBAL CLOUD SOLUTIONS INC\n"
            "VAT ID: US-987654321\n"
            "Address: 500 Tech Blvd, Austin, TX, USA\n"
            "INVOICE\n"
            "Invoice #: INV-2026-6006\n"
            "Date: 2026-10-06\n"
            "Bill To: ANDES TECH LABS SAS\n"
            "Customer ID: CUST-7788\n"
            "Dedicated Cloud Server Hosting  1  500.00  500.00\n"
            "Database Backup & Replication  1  200.00  200.00\n"
            "Subtotal: $ 700.00\n"
            "Tax (10%): $ 70.00\n"
            "Grand Total: $ 770.00\n"
        ),
    }

    for name, content in fixtures.items():
        (FIXTURES_DIR / name).write_text(content, encoding="utf-8")


def main():
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Generando facturas ficticias en: {FIXTURES_DIR}")

    generar_factura_1_limpia(FIXTURES_DIR / "factura_1_limpia.pdf")
    generar_factura_2_ruido(FIXTURES_DIR / "factura_2_ruido.pdf")
    generar_factura_3_multipage(FIXTURES_DIR / "factura_3_multipage.pdf")
    generar_factura_4_descuadre(FIXTURES_DIR / "factura_4_descuadre.pdf")
    generar_factura_5_sin_nit(FIXTURES_DIR / "factura_5_sin_nit.pdf")
    generar_factura_6_ingles(FIXTURES_DIR / "factura_6_ingles.pdf")

    generar_text_fixtures()
    print("6 facturas PDF ficticias y sus fixtures de texto generados exitosamente.")


if __name__ == "__main__":
    main()
