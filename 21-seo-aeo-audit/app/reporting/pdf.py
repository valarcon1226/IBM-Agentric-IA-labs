"""PDF generation from HTML report using headless Microsoft Edge or Chrome."""

import os
import subprocess
import tempfile

from app.lighthouse import find_browser_executable


def generate_pdf_from_html(
    html_content: str,
    output_pdf_path: str,
    timeout_seconds: int = 30,
) -> str:
    """
    Export the HTML report to a PDF document using headless browser printing.
    """
    browser_bin = find_browser_executable()
    if not browser_bin:
        raise RuntimeError("No se encontró Microsoft Edge ni Chrome en el sistema para generar el PDF.")

    abs_output = os.path.abspath(output_pdf_path)
    output_dir = os.path.dirname(abs_output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    with tempfile.NamedTemporaryFile("w", suffix=".html", encoding="utf-8", delete=False) as tmp:
        tmp.write(html_content)
        tmp_html_path = tmp.name

    try:
        cmd = [
            browser_bin,
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={abs_output}",
            tmp_html_path,
        ]

        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=True,
        )

        if not os.path.exists(abs_output) or os.path.getsize(abs_output) == 0:
            raise RuntimeError(f"El navegador no generó el archivo PDF en '{abs_output}'.")

        return abs_output

    finally:
        if os.path.exists(tmp_html_path):
            try:
                os.remove(tmp_html_path)
            except OSError:
                pass
