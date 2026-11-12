"""Business logic validation for invoices."""

import re
from decimal import Decimal
from typing import Any

from app.services.extractor import ExtractedInvoice


class InvoiceValidator:
    """Validates required fields, VAT format, and mathematical consistency."""

    TOLERANCE = Decimal("1.50")  # Rounding tolerance for currency totals

    def validate_colombian_nit_dv(self, nit_body: str, dv: str) -> bool:
        """Validates Colombian DIAN Verification Digit (Dígito de Verificación).

        Weights: 71, 67, 59, 53, 47, 41, 37, 29, 23, 19, 17, 13, 7, 3
        """
        weights = [3, 7, 13, 17, 19, 23, 29, 37, 41, 47, 53, 59, 67, 71]
        digits = [int(c) for c in nit_body if c.isdigit()]
        if not digits:
            return False

        # Apply weights from right to left
        weighted_sum = sum(d * w for d, w in zip(reversed(digits), weights, strict=False))
        remainder = weighted_sum % 11
        if remainder in (0, 1):
            expected_dv = remainder
        else:
            expected_dv = 11 - remainder

        return str(expected_dv) == dv.strip()

    def validate_vat_format(self, vat: str | None) -> tuple[bool, str | None]:
        """Validates format for Colombian NIT or international VAT ID."""
        if not vat:
            return False, "Falta el NIT/VAT del emisor"

        cleaned = vat.strip()

        # Check Colombian NIT format (e.g. 900.123.456-7 or 900123456-7)
        colombian_match = re.match(r"^(\d{1,3}(?:\.\d{3}){2}|\d{8,10})-(\d)$", cleaned)
        if colombian_match:
            body = colombian_match.group(1).replace(".", "")
            dv = colombian_match.group(2)
            if not self.validate_colombian_nit_dv(body, dv):
                return False, f"Dígito de verificación inválido para el NIT '{cleaned}'"
            return True, None

        # General Colombian NIT without dash (9-10 digits)
        if re.match(r"^\d{9,10}$", cleaned):
            return True, None

        # General international VAT / Tax ID (e.g. US-987654321, ESA12345678, GB123456789)
        if re.match(r"^[A-Z0-9\-]{5,20}$", cleaned, re.IGNORECASE):
            return True, None

        return False, f"Formato de NIT/VAT no reconocido: '{cleaned}'"

    def validate(self, invoice: ExtractedInvoice | dict[str, Any]) -> tuple[bool, list[str]]:
        """Runs all validation rules and returns (is_valid, validation_errors)."""
        errors: list[str] = []

        # Helper accessors
        if isinstance(invoice, ExtractedInvoice):
            issuer_name = invoice.issuer_name
            issuer_vat = invoice.issuer_vat
            invoice_number = invoice.invoice_number
            invoice_date = invoice.invoice_date
            subtotal = invoice.subtotal
            tax_rate = invoice.tax_rate
            tax_amount = invoice.tax_amount
            total = invoice.total
            line_items = invoice.line_items
        else:
            issuer_name = invoice.get("issuer_name")
            issuer_vat = invoice.get("issuer_vat")
            invoice_number = invoice.get("invoice_number")
            invoice_date = invoice.get("invoice_date")
            subtotal = (
                Decimal(str(invoice["subtotal"])) if invoice.get("subtotal") is not None else None
            )
            tax_rate = (
                Decimal(str(invoice["tax_rate"])) if invoice.get("tax_rate") is not None else None
            )
            tax_amount = (
                Decimal(str(invoice["tax_amount"]))
                if invoice.get("tax_amount") is not None
                else None
            )
            total = Decimal(str(invoice["total"])) if invoice.get("total") is not None else None
            line_items = invoice.get("line_items", [])

        # 1. Required Fields
        if not issuer_name or not str(issuer_name).strip():
            errors.append("Campo obligatorio faltante: emisor (issuer_name)")
        if not invoice_number or not str(invoice_number).strip():
            errors.append("Campo obligatorio faltante: número de factura (invoice_number)")
        if not invoice_date:
            errors.append("Campo obligatorio faltante: fecha de emisión (invoice_date)")
        if total is None:
            errors.append("Campo obligatorio faltante: total de la factura")

        # 2. Issuer NIT/VAT Validation
        is_vat_valid, vat_err = self.validate_vat_format(issuer_vat)
        if not is_vat_valid and vat_err:
            errors.append(vat_err)

        # 3. Tax Calculation Verification: subtotal * (tax_rate / 100) ≈ tax_amount
        if subtotal is not None and tax_rate is not None and tax_amount is not None:
            expected_tax = subtotal * (tax_rate / Decimal("100"))
            if abs(expected_tax - tax_amount) > self.TOLERANCE:
                errors.append(
                    f"Descuadre en impuesto: subtotal ({subtotal}) * tasa ({tax_rate}%) = "
                    f"{expected_tax:.2f}, pero se declaró {tax_amount}"
                )

        # 4. Total Verification: subtotal + tax_amount ≈ total
        if subtotal is not None and tax_amount is not None and total is not None:
            expected_total = subtotal + tax_amount
            if abs(expected_total - total) > self.TOLERANCE:
                errors.append(
                    f"Descuadre en total: subtotal ({subtotal}) + impuesto ({tax_amount}) = "
                    f"{expected_total:.2f}, pero se declaró total {total}"
                )
        elif subtotal is not None and total is not None and tax_amount is None:
            # If no tax, subtotal should equal total
            if abs(subtotal - total) > self.TOLERANCE:
                errors.append(
                    f"Descuadre en total sin impuesto: subtotal ({subtotal}) != total ({total})"
                )

        # 5. Line items consistency
        for idx, item in enumerate(line_items, start=1):
            if isinstance(item, dict):
                qty = Decimal(str(item["quantity"])) if item.get("quantity") is not None else None
                price = (
                    Decimal(str(item["unit_price"])) if item.get("unit_price") is not None else None
                )
                ltotal = (
                    Decimal(str(item["line_total"])) if item.get("line_total") is not None else None
                )
                desc = item.get("description", f"Ítem {idx}")
            else:
                qty = item.quantity
                price = item.unit_price
                ltotal = item.line_total
                desc = item.description

            if qty is not None and price is not None and ltotal is not None:
                expected_line = qty * price
                if abs(expected_line - ltotal) > self.TOLERANCE:
                    errors.append(
                        f"Descuadre en ítem '{desc}': cantidad ({qty}) * precio ({price}) = "
                        f"{expected_line:.2f}, pero se declaró {ltotal}"
                    )

        is_valid = len(errors) == 0
        return is_valid, errors


validator = InvoiceValidator()
