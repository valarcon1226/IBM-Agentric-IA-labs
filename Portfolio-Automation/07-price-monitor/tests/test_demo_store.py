"""Unit tests for the demo-store update_price.py script."""

import importlib.util
from pathlib import Path


def _get_update_price_fn():
    script_path = Path(__file__).resolve().parent.parent / "demo-store" / "update_price.py"
    spec = importlib.util.spec_from_file_location("update_price", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.update_price_in_html


def test_update_price_modifies_json_ld_and_html(tmp_path: Path):
    update_price_in_html = _get_update_price_fn()

    sample_html = """<!DOCTYPE html>
<html>
<head>
    <script type="application/ld+json">
    {
      "@type": "Product",
      "name": "Headphones",
      "offers": {
        "price": "85.00"
      }
    }
    </script>
</head>
<body>
    <span id="product-price" class="price" data-currency="USD">$85.00</span>
</body>
</html>"""

    test_file = tmp_path / "test_item.html"
    test_file.write_text(sample_html, encoding="utf-8")

    success = update_price_in_html(test_file, 59.99)
    assert success is True

    updated_content = test_file.read_text(encoding="utf-8")
    assert '"price": "59.99"' in updated_content
    assert "$59.99</span>" in updated_content
