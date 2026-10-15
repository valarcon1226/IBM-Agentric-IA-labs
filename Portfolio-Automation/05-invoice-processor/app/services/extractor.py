"""Rule-based text extraction service for invoices."""

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal


@dataclass
class ExtractedLineItem:
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


@dataclass
class ExtractedInvoice:
    issuer_name: str | None = None
    issuer_vat: str | None = None
    recipient_name: str | None = None
    recipient_vat: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    subtotal: Decimal | None = None
    tax_rate: Decimal | None = None
    tax_amount: Decimal | None = None
    total: Decimal | None = None
    currency: str | None = "COP"
    line_items: list[ExtractedLineItem] = field(default_factory=list)


def clean_number_str(raw: str) -> str:
    """Removes currency symbols and extraneous whitespace."""
    s = re.sub(r"[^\d.,\-]", "", raw).strip()
    return s


def parse_decimal(raw: str | None) -> Decimal | None:
    """Parses numeric amount supporting both dot and comma decimal notations."""
    if not raw:
        return None
    cleaned = clean_number_str(raw)
    if not cleaned:
        return None

    try:
        # Both dot and comma present
        if "." in cleaned and "," in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                # Format: 1.250.000,50
                normalized = cleaned.replace(".", "").replace(",", ".")
            else:
                # Format: 1,250,000.50
                normalized = cleaned.replace(",", "")
            return Decimal(normalized)

        # Only comma present
        if "," in cleaned:
            parts = cleaned.split(",")
            if len(parts[-1]) == 2:
                # Format: 1500,50
                normalized = cleaned.replace(",", ".")
            else:
                # Format: 1,500,000
                normalized = cleaned.replace(",", "")
            return Decimal(normalized)

        # Only dot present
        if "." in cleaned:
            parts = cleaned.split(".")
            # If last part is 3 digits and multiple dots exist, thousands separator
            if len(parts) > 2 or (len(parts) == 2 and len(parts[-1]) == 3 and int(parts[0]) > 0):
                normalized = cleaned.replace(".", "")
            else:
                normalized = cleaned
            return Decimal(normalized)

        return Decimal(cleaned)
    except Exception:
        return None


def parse_date(raw: str | None) -> date | None:
    """Parses date string into date object."""
    if not raw:
        return None
    cleaned = raw.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


class InvoiceExtractor:
    """Extracts structured invoice information from raw OCR text using regex and heuristics."""

    def extract(self, text: str) -> ExtractedInvoice:
        invoice = ExtractedInvoice()
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        # Determine currency
        if any(term in text for term in ("USD", "US $", "USA", "US-", "INVOICE", "Grand Total")):
            invoice.currency = "USD"
        elif "EUR" in text or "€" in text:
            invoice.currency = "EUR"
        else:
            invoice.currency = "COP"

        # 1. Invoice Number
        inv_no_pattern = re.compile(
            r"(?:factura\s*(?:electr[oó]nica\s*)?(?:de\s*venta\s*)?(?:n[oó]\.?|n°|#)?|invoice\s*(?:n[oó]\.?|#)?)\s*:?\s*([A-Za-z0-9\-]+)",
            re.IGNORECASE,
        )
        for line in lines:
            m = inv_no_pattern.search(line)
            if m:
                val = m.group(1).strip()
                if val.lower() not in ("de", "electrónica", "electronica", "venta", "no", "date"):
                    invoice.invoice_number = val
                    break

        # 2. Issuer VAT (NIT or VAT ID)
        nit_pattern = re.compile(
            r"(?:nit|vat(?:\s*id)?|rut|tax\s*id)\s*(?:emisor|proveedor)?\s*:?\s*([0-9]{1,3}(?:\.[0-9]{3}){2}-[0-9]|[0-9]{9,10}-[0-9]|[0-9]{9,10}|[A-Z0-9\-]{7,15})",
            re.IGNORECASE,
        )
        for line in lines:
            m = nit_pattern.search(line)
            if m:
                invoice.issuer_vat = m.group(1).strip()
                break

        # 3. Issuer Name
        # Check explicit label or first prominent line
        issuer_label_pattern = re.compile(
            r"(?:emisor|raz[oó]n\s*social|proveedor|company|issuer)\s*:?\s*([A-Za-z0-9ÁÉÍÓÚáéíóúñÑ\s.,&'-]+)",
            re.IGNORECASE,
        )
        for line in lines[:8]:
            m = issuer_label_pattern.search(line)
            if m:
                name = m.group(1).strip()
                if len(name) > 3:
                    invoice.issuer_name = name
                    break

        if not invoice.issuer_name:
            # Fallback heuristic: First non-metadata line
            for line in lines[:8]:
                cleaned = re.sub(
                    r"\s+\b(?:factura|invoice|de\s*venta|electr[oó]nica)\b.*$",
                    "",
                    line,
                    flags=re.IGNORECASE,
                ).strip()
                if (
                    not re.search(
                        r"\b(?:factura|invoice|nit|fecha|date|p[aá]gina|page|tel|direcci[oó]n|"
                        r"address|documento|ficticio|legal|validez|datos|cliente|adquirente|customer)\b",
                        cleaned,
                        re.IGNORECASE,
                    )
                    and len(cleaned) > 3
                ):
                    invoice.issuer_name = cleaned
                    break

        # 4. Recipient Name & VAT
        recipient_name_pattern = re.compile(
            r"(?:se[nñ]or(?:es)?|cliente|adquirente|bill\s*to|customer|recipient)\s*:?\s*([A-Za-z0-9ÁÉÍÓÚáéíóúñÑ\s.,&'-]+)",
            re.IGNORECASE,
        )
        recipient_vat_pattern = re.compile(
            r"(?:nit|cc|c\.c\.|id|vat)\s*(?:cliente|adquirente|comprador|recipient)?\s*:?\s*([0-9]{1,3}(?:\.[0-9]{3}){2}-[0-9]|[0-9]{6,12}-[0-9]|[0-9]{6,12})",
            re.IGNORECASE,
        )
        for line in lines:
            if not invoice.recipient_name:
                m = recipient_name_pattern.search(line)
                if m:
                    r_name = m.group(1).strip()
                    if len(r_name) > 2 and not re.search(
                        r"^(nit|cc|fecha|date)", r_name, re.IGNORECASE
                    ):
                        invoice.recipient_name = r_name
            if not invoice.recipient_vat:
                # Ensure it's not the issuer VAT line
                if "emisor" not in line.lower() and (
                    not invoice.issuer_vat or invoice.issuer_vat not in line
                ):
                    m = recipient_vat_pattern.search(line)
                    if m and m.group(1).strip() != invoice.issuer_vat:
                        invoice.recipient_vat = m.group(1).strip()

        # 5. Dates
        date_pattern = re.compile(
            r"(?:fecha\s*(?:de\s*emisi[oó]n)?|date|invoice\s*date)\s*:?\s*([0-9]{4}[-/][0-9]{2}[-/][0-9]{2}|[0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{4})",
            re.IGNORECASE,
        )
        due_date_pattern = re.compile(
            r"(?:fecha\s*(?:de\s*)?vencimiento|due\s*date)\s*:?\s*([0-9]{4}[-/][0-9]{2}[-/][0-9]{2}|[0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{4})",
            re.IGNORECASE,
        )
        for line in lines:
            if not invoice.invoice_date:
                m = date_pattern.search(line)
                if m and "vencimiento" not in line.lower() and "due" not in line.lower():
                    invoice.invoice_date = parse_date(m.group(1))
            if not invoice.due_date:
                m = due_date_pattern.search(line)
                if m:
                    invoice.due_date = parse_date(m.group(1))

        if not invoice.invoice_date:
            standalone_date = re.compile(
                r"\b([0-9]{4}[-/][0-9]{2}[-/][0-9]{2}|[0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{4})\b"
            )
            for line in lines:
                m = standalone_date.search(line)
                if m:
                    parsed = parse_date(m.group(1))
                    if parsed:
                        invoice.invoice_date = parsed
                        break

        # 6. Totals & Tax
        subtotal_pattern = re.compile(
            r"\b(?:subtotal|sub-total|sub\s*total)[\s:$]*([0-9.,]+)",
            re.IGNORECASE,
        )
        tax_pattern = re.compile(
            r"\b(?:iva|tax|impuesto)(?:\s*\(\s*([0-9]+(?:\.[0-9]+)?)\s*%\s*\)|\s*([0-9]+(?:\.[0-9]+)?)\s*%)?[\s:$]*([0-9.,]+)?",
            re.IGNORECASE,
        )
        total_pattern = re.compile(
            r"\b(?:total(?:\s*a\s*pagar)?|grand\s*total|importe\s*total)[\s:$]*([0-9.,]+)",
            re.IGNORECASE,
        )

        for i, line in enumerate(lines):
            candidate = line
            if i + 1 < len(lines):
                candidate = f"{line} {lines[i + 1]}"

            if invoice.subtotal is None:
                m = subtotal_pattern.search(line) or subtotal_pattern.search(candidate)
                if m:
                    invoice.subtotal = parse_decimal(m.group(1))

            if invoice.tax_amount is None or invoice.tax_rate is None:
                m = tax_pattern.search(line) or tax_pattern.search(candidate)
                if m:
                    rate_val = m.group(1) or m.group(2)
                    amt_val = m.group(3)
                    if rate_val and invoice.tax_rate is None:
                        invoice.tax_rate = parse_decimal(rate_val)
                    if amt_val and invoice.tax_amount is None:
                        invoice.tax_amount = parse_decimal(amt_val)

            if invoice.total is None:
                if not re.search(r"\bsub[- ]?total\b", line, re.IGNORECASE):
                    m = total_pattern.search(line)
                    if m:
                        invoice.total = parse_decimal(m.group(1))
                elif not re.search(r"\bsub[- ]?total\b", candidate, re.IGNORECASE):
                    m = total_pattern.search(candidate)
                    if m:
                        invoice.total = parse_decimal(m.group(1))

        # 7. Line Items extraction heuristic
        # Matches lines with: Description, Quantity, Unit Price, Line Total
        # E.g.: "Consultoria TI | 10 | 150000 | 1500000" or "Soporte  2  50.000  100.000"
        item_table_pattern = re.compile(
            r"^([A-Za-z0-9ÁÉÍÓÚáéíóúñÑ\s\-_/&.]+?)\s+[|,]?\s*(\d+(?:\.\d+)?)\s+[|,]?\s*([0-9.,]+)\s+[|,]?\s*([0-9.,]+)$"
        )
        for line in lines:
            # Skip header or summary lines
            if re.search(
                r"(descripci[oó]n|cantidad|precio|total|subtotal|iva|tax|nit|fecha|date|se[nñ]or|cliente)",
                line,
                re.IGNORECASE,
            ):
                continue
            m = item_table_pattern.match(line)
            if m:
                desc = m.group(1).strip()
                qty = parse_decimal(m.group(2))
                unit = parse_decimal(m.group(3))
                ltotal = parse_decimal(m.group(4))
                if desc and qty and unit and ltotal and len(desc) > 2:
                    invoice.line_items.append(
                        ExtractedLineItem(
                            description=desc,
                            quantity=qty,
                            unit_price=unit,
                            line_total=ltotal,
                        )
                    )

        return invoice


extractor = InvoiceExtractor()
