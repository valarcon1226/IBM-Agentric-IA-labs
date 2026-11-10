"""Export service for invoices to CSV."""

import csv
import io
from collections.abc import Sequence

from app.models.database import Invoice


class ExporterService:
    """Exports invoice database records to CSV string format."""

    @staticmethod
    def to_csv(invoices: Sequence[Invoice]) -> str:
        output = io.StringIO()
        writer = csv.writer(output)

        headers = [
            "invoice_id",
            "invoice_number",
            "issuer_name",
            "issuer_vat",
            "recipient_name",
            "recipient_vat",
            "invoice_date",
            "due_date",
            "subtotal",
            "tax_rate",
            "tax_amount",
            "total",
            "currency",
            "is_valid",
            "validation_errors",
            "status",
            "created_at",
        ]
        writer.writerow(headers)

        for inv in invoices:
            err_str = "; ".join(inv.validation_errors) if inv.validation_errors else ""
            writer.writerow(
                [
                    str(inv.invoice_id),
                    inv.invoice_number or "",
                    inv.issuer_name or "",
                    inv.issuer_vat or "",
                    inv.recipient_name or "",
                    inv.recipient_vat or "",
                    inv.invoice_date.isoformat() if inv.invoice_date else "",
                    inv.due_date.isoformat() if inv.due_date else "",
                    str(inv.subtotal) if inv.subtotal is not None else "",
                    str(inv.tax_rate) if inv.tax_rate is not None else "",
                    str(inv.tax_amount) if inv.tax_amount is not None else "",
                    str(inv.total) if inv.total is not None else "",
                    inv.currency or "",
                    "TRUE" if inv.is_valid else "FALSE",
                    err_str,
                    inv.status,
                    inv.created_at.isoformat() if inv.created_at else "",
                ]
            )

        return output.getvalue()


exporter = ExporterService()
