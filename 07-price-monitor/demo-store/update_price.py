"""Utility script to change product prices in the demo store HTML files.

Updates both the JSON-LD structured data and the HTML CSS price element.

Usage:
    python update_price.py <product_name_or_path> <new_price>
Example:
    python update_price.py headphones 65.00
    python update_price.py keyboard 99.99
"""

import argparse
import re
import sys
from pathlib import Path


def update_price_in_html(file_path: Path, new_price: float) -> bool:
    if not file_path.exists():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        return False

    content = file_path.read_text(encoding="utf-8")
    formatted_price = f"{new_price:.2f}"

    # 1. Update JSON-LD: "price": "..."
    json_ld_pattern = r'("price"\s*:\s*")([^"]+)(")'
    new_content, count_json = re.subn(json_ld_pattern, rf"\g<1>{formatted_price}\g<3>", content)

    # 2. Update HTML price span: <span ... class="price" ...>$...</span>
    html_pattern = r'(<span[^>]*id=["\']product-price["\'][^>]*>)[^<]*(</span>)'
    new_content, count_html = re.subn(html_pattern, rf"\g<1>${formatted_price}\g<2>", new_content)

    if count_json == 0 and count_html == 0:
        print(f"Warning: No price patterns matched in {file_path}", file=sys.stderr)
        return False

    file_path.write_text(new_content, encoding="utf-8")
    print(
        f"Updated {file_path.name} price to ${formatted_price} (JSON-LD: {count_json}, HTML: {count_html})"
    )
    return True


def resolve_file(target: str) -> Path:
    p = Path(target)
    if p.exists() and p.is_file():
        return p

    # Check relative to script directory
    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir / "html" / "products" / f"{target}.html",
        script_dir / "html" / "products" / target,
        script_dir / "html" / target,
        Path("demo-store/html/products") / f"{target}.html",
        Path("07-price-monitor/demo-store/html/products") / f"{target}.html",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c

    # Fallback to direct path
    return p


def main() -> None:
    parser = argparse.ArgumentParser(description="Update product price in demo store HTML files.")
    parser.add_argument(
        "product", help="Product name (e.g. 'headphones', 'keyboard') or path to HTML file"
    )
    parser.add_argument("price", type=float, help="New price (e.g. 65.00)")

    args = parser.parse_args()
    file_path = resolve_file(args.product)

    success = update_price_in_html(file_path, args.price)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
