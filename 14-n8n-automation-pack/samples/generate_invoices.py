"""Generates the sample invoice PDFs used by F2's demo/tests (DECISIONES-14 B2).

No PDF library: a single-page PDF with one Helvetica text stream is simple enough to hand-write
with just the stdlib, and it's what n8n's "Extract From File" node (pdfjs-dist under the hood)
needs to pull back plain text. Only reach for a pinned PDF library (`requirements-dev.txt`) if a
sample ever needs more than flat text on one page.

Run with ``python samples/generate_invoices.py`` from the project root. Re-run any time to
regenerate the three fixtures below; nothing else in the repo depends on their exact bytes.
"""

from pathlib import Path

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
FONT_SIZE = 11
LINE_HEIGHT = 16
TOP_MARGIN = 740
LEFT_MARGIN = 72


def _escape(text: str) -> bytes:
    escaped = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    return escaped.encode("cp1252", errors="replace")


def _content_stream(lines: list[str]) -> bytes:
    parts = [
        b"BT",
        f"/F1 {FONT_SIZE} Tf".encode(),
        f"{LEFT_MARGIN} {TOP_MARGIN} Td".encode(),
        f"{LINE_HEIGHT} TL".encode(),
    ]
    for index, line in enumerate(lines):
        if index > 0:
            parts.append(b"T*")
        parts.append(b"(" + _escape(line) + b") Tj")
    parts.append(b"ET")
    return b"\n".join(parts)


def build_pdf(lines: list[str]) -> bytes:
    """Builds a minimal, valid single-page PDF (Helvetica, WinAnsi) containing ``lines`` of text."""
    content = _content_stream(lines)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        )
        % (PAGE_WIDTH, PAGE_HEIGHT),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
    ]

    buf = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(buf))
        buf += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_offset = len(buf)
    buf += f"xref\n0 {len(objects) + 1}\n".encode()
    buf += b"0000000000 65535 f \n"
    for offset in offsets:
        buf += f"{offset:010d} 00000 n \n".encode()
    buf += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF"
    ).encode()
    return bytes(buf)


INVOICE_VALID = [
    "FACTURA DE VENTA",
    "Proveedor: Distribuidora La Sabana SAS",
    "NIT: 900123456-7",
    "Fecha: 2026-09-30",
    "Items:",
    "- Tomate chonto x 20 = 60000",
    "- Cebolla cabezona x 15 = 45000",
    "- Papa criolla x 30 = 90000",
    "Subtotal: 195000",
    "IVA: 37050",
    "Total: 232050",
]

INVOICE_BAD_TOTALS = [
    "FACTURA DE VENTA",
    "Proveedor: Carnes El Novillo Ltda",
    "NIT: 800456789-2",
    "Fecha: 2026-09-28",
    "Items:",
    "- Carne de res x 25 = 375000",
    "- Pollo entero x 10 = 90000",
    "Subtotal: 465000",
    "IVA: 88350",
    "Total: 999999",
]

INVOICE_BAD_DATE = [
    "FACTURA DE VENTA",
    "Proveedor: Verduras Frescas del Valle",
    "NIT: 700987654-1",
    "Fecha: 2026-13-45",
    "Items:",
    "- Lechuga x 12 = 24000",
    "- Zanahoria x 18 = 27000",
    "Subtotal: 51000",
    "IVA: 9690",
    "Total: 60690",
]

FIXTURES = {
    "factura-valida.pdf": INVOICE_VALID,
    "factura-totales-no-cuadran.pdf": INVOICE_BAD_TOTALS,
    "factura-fecha-invalida.pdf": INVOICE_BAD_DATE,
}


def main() -> None:
    out_dir = Path(__file__).resolve().parent
    for filename, lines in FIXTURES.items():
        (out_dir / filename).write_bytes(build_pdf(lines))
        print(f"wrote {filename}")


if __name__ == "__main__":
    main()
