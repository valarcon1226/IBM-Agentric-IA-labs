"""Single source of truth for the ~40 fictional Bogotá businesses in ../../demo-directory/
(DECISIONES-08 L2). `scripts/generate_demo_directory.py` renders this into static HTML; the
adapter tests assert against it directly so the fixtures and the expectations never drift apart.

Each entry:
  category   - "restaurantes" | "contadores" | "clinicas-dentales"
  page        - 1 or 2 (clinicas-dentales has a single JS-rendered page -> always 1)
  name        - company_name as it appears on the card
  phone       - raw phone exactly as printed (mixed Colombian formats, DECISIONES-08 L2)
  address     - address_raw
  site        - website slug under demo-directory/sitios/, or None (no website)
  site_email  - email shown on that site's contacto.html, or None (site exists but no email)

`clinicas-dentales` cards are NOT present in the raw HTML (rendered by the inline <script>,
simulating a JS-only listing) — see demo-directory/clinicas-dentales/index.html.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Business:
    category: str
    page: int
    name: str
    phone: str
    address: str
    site: str | None = None
    site_email: str | None = None


BUSINESSES: list[Business] = [
    # -- restaurantes: page 1 (8) --
    Business(
        "restaurantes",
        1,
        "Restaurante El Buen Sabor",
        "(601) 234-5678",
        "Cra 7 # 45-10, Bogotá",
        "restaurante-el-buen-sabor",
        "contacto@elbuensabor.com.co",
    ),
    Business(
        "restaurantes", 1, "Asadero La Brasa Dorada", "3012345678", "Calle 80 # 12-34, Bogotá"
    ),
    Business(
        "restaurantes",
        1,
        "Restaurante Doña Rosa",
        "301-234-5679",
        "Cra 15 # 67-20, Bogotá",
        "restaurante-dona-rosa",
        "info@donarosa.com.co",
    ),
    Business(
        "restaurantes",
        1,
        "Pastelería y Cafetería Dulce Hogar",
        "+57 300 234 5680",
        "Calle 53 # 9-15, Bogotá",
        "panaderia-dulce-hogar",
        "ventas@dulcehogar.com.co",
    ),
    Business(
        "restaurantes", 1, "Restaurante El Fogón Paisa", "(1) 345-6781", "Cra 24 # 50-02, Bogotá"
    ),
    Business(
        "restaurantes",
        1,
        "Comidas Rápidas El Buen Sabor II",
        "3202345678",
        "Calle 19 # 4-56, Bogotá",
    ),
    Business(
        "restaurantes",
        1,
        "Restaurante La Fonda Antioqueña",
        "3156789012",
        "Cra 30 # 18-40, Bogotá",
        "la-fonda-antioquena",
        None,
    ),
    Business("restaurantes", 1, "Panadería San José", "+57 1 456 7890", "Calle 72 # 11-20, Bogotá"),
    # -- restaurantes: page 2 (6) --
    Business(
        "restaurantes",
        2,
        "Restaurante El Buen Sabor SAS",
        "601 234 5678",
        "Cra 7 # 45-10, Bogotá",
        "restaurante-el-buen-sabor",
        "contacto@elbuensabor.com.co",
    ),
    Business(
        "restaurantes",
        2,
        "Restaurante Sabor Costeño",
        "3178889900",
        "Calle 100 # 15-30, Bogotá",
        "sabor-costeno",
        "hola@saborcosteno.com.co",
    ),
    Business("restaurantes", 2, "Cevichería El Puerto", "3011122334", "Cra 50 # 22-11, Bogotá"),
    Business(
        "restaurantes",
        2,
        "Restaurante Parrilla Los Amigos",
        "(601) 567-8901",
        "Calle 63 # 8-90, Bogotá",
        "parrilla-los-amigos",
        "contacto@parrillalosamigos.com.co",
    ),
    Business(
        "restaurantes",
        2,
        "Café Internet y Panadería La Esquina",
        "3123456789",
        "Cra 11 # 33-45, Bogotá",
    ),
    Business(
        "restaurantes", 2, "Restaurante Doña Rosa S.A.S", "301 234 5679", "Cra 15 # 67-20, Bogotá"
    ),
    # -- contadores: page 1 (7) --
    Business(
        "contadores",
        1,
        "Contadores Ruiz SAS",
        "+57 601 7890123",
        "Calle 90 # 13-20, Bogotá",
        "contadores-ruiz",
        "info@contadoresruiz.com.co",
    ),
    Business(
        "contadores",
        1,
        "Asesorías Contables del Norte",
        "3134567890",
        "Cra 45 # 100-12, Bogotá",
        "asesorias-contables-del-norte",
        "contacto@acnorte.com.co",
    ),
    Business(
        "contadores", 1, "Contabilidad y Impuestos López", "3045678901", "Calle 26 # 68-30, Bogotá"
    ),
    Business(
        "contadores",
        1,
        "Firma Contable Andina",
        "(1) 678-9012",
        "Cra 13 # 85-40, Bogotá",
        "firma-contable-andina",
        "info@contableandina.com.co",
    ),
    Business(
        "contadores", 1, "Contadores Públicos Asociados", "3156677889", "Calle 34 # 7-18, Bogotá"
    ),
    Business(
        "contadores",
        1,
        "Servicios Tributarios Bogotá",
        "3187788990",
        "Cra 68 # 25-60, Bogotá",
        "servicios-tributarios-bogota",
        "info@tributariosbogota.com.co",
    ),
    Business(
        "contadores", 1, "Contabilidad Integral del Centro", "3019988776", "Calle 17 # 4-80, Bogotá"
    ),
    # -- contadores: page 2 (6) --
    Business(
        "contadores",
        2,
        "Contadores Ruiz S.A.S.",
        "601 789 0123",
        "Calle 90 # 13-20, Bogotá",
        "contadores-ruiz",
        "info@contadoresruiz.com.co",
    ),
    Business(
        "contadores",
        2,
        "Asesoría Fiscal y Contable Sur",
        "3145566778",
        "Cra 27 # 48-15, Bogotá",
        "asesoria-fiscal-contable-sur",
        "contacto@fiscalsur.com.co",
    ),
    Business(
        "contadores", 2, "Contadores Unidos de Colombia", "3167654321", "Calle 45 # 20-33, Bogotá"
    ),
    Business(
        "contadores",
        2,
        "Auditores y Contadores Prieto",
        "3192233445",
        "Cra 7 # 116-30, Bogotá",
        "auditores-contadores-prieto",
        None,
    ),
    Business("contadores", 2, "Contabilidad Express", "(601) 890-1234", "Calle 53 # 30-10, Bogotá"),
    Business(
        "contadores", 2, "Impuestos y Contabilidad Familiar", "3078899001", "Cra 19 # 60-22, Bogotá"
    ),
    # -- clinicas-dentales: single JS-rendered page (13) --
    Business(
        "clinicas-dentales",
        1,
        "Clínica Dental Sonrisas",
        "3011234567",
        "Calle 72 # 10-34, Bogotá",
        "clinica-dental-sonrisas",
        "citas@sonrisas.com.co",
    ),
    Business(
        "clinicas-dentales",
        1,
        "Odontología Integral Bogotá",
        "3023456789",
        "Cra 15 # 88-20, Bogotá",
        "odontologia-integral-bogota",
        "contacto@odontointegral.com.co",
    ),
    Business(
        "clinicas-dentales",
        1,
        "Clínica Dental Nueva Imagen",
        "(601) 901-2345",
        "Calle 100 # 19-61, Bogotá",
    ),
    Business(
        "clinicas-dentales",
        1,
        "Consultorio Dental Dra. Martínez",
        "3134455667",
        "Cra 24 # 53-12, Bogotá",
    ),
    Business(
        "clinicas-dentales",
        1,
        "Clínica Odontológica del Norte",
        "3145566778",
        "Calle 134 # 7-45, Bogotá",
    ),
    Business(
        "clinicas-dentales",
        1,
        "Clínica Dental Sonrisas SAS",
        "301 123 4567",
        "Calle 72 # 10-34, Bogotá",
        "clinica-dental-sonrisas",
        "citas@sonrisas.com.co",
    ),
    Business(
        "clinicas-dentales",
        1,
        "Odontología Especializada El Dorado",
        "3156789023",
        "Cra 50 # 26-80, Bogotá",
        "odontologia-especializada-el-dorado",
        "info@eldoradodental.com.co",
    ),
    Business(
        "clinicas-dentales", 1, "Clínica Dental Familiar", "3167890234", "Calle 63 # 16-22, Bogotá"
    ),
    Business(
        "clinicas-dentales",
        1,
        "Consultorio Odontológico Vida Sana",
        "3178901345",
        "Cra 30 # 45-10, Bogotá",
    ),
    Business(
        "clinicas-dentales",
        1,
        "Clínica Dental Avanzada",
        "3189012456",
        "Calle 80 # 20-15, Bogotá",
        "clinica-dental-avanzada",
        "info@dentalavanzada.com.co",
    ),
    Business(
        "clinicas-dentales",
        1,
        "Odontología Estética y Funcional",
        "3190123567",
        "Cra 11 # 95-30, Bogotá",
    ),
    Business(
        "clinicas-dentales",
        1,
        "Centro de Especialistas Dentales",
        "3101234678",
        "Calle 45 # 13-50, Bogotá",
    ),
    Business(
        "clinicas-dentales",
        1,
        "Clínica Dental El Bosque",
        "3112345789",
        "Cra 7 # 134-20, Bogotá",
        "clinica-dental-el-bosque",
        "contacto@dentalelbosque.com.co",
    ),
]

CATEGORY_LABELS = {
    "restaurantes": "Restaurantes",
    "contadores": "Contadores",
    "clinicas-dentales": "Clínicas Dentales",
}
