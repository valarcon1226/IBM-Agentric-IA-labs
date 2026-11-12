"""Deterministic, labeled PDF corpus generator for Paperless-ngx testing.

Generates 600 text-layer PDFs across 5 document types and 12 correspondents,
with realistic fields (3 date formats, comma/dot decimals, IBAN accounts),
including 3% corrupt files and 2% exact duplicates.
Produces corpus/labels.csv and corpus/manifest.sha256.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

from fpdf import FPDF

DOCUMENT_TYPES = [
    "invoice",
    "purchase_order",
    "bank_statement",
    "utility_bill",
    "letter",
]

CORRESPONDENTS = [
    "Acme Corp",
    "Apex Logistics",
    "Beacon Energy",
    "City Utilities",
    "Global Financial",
    "Horizon Bank",
    "Metro Telecom",
    "Nexus Hardware",
    "Omega Supplies",
    "Pinnacle Advisory",
    "Quantum Retail",
    "Vertex Services",
]

IBAN_PREFIXES = [
    ("DE", "DE89 3704 0044 0532 "),
    ("GB", "GB29 NWBK 6016 1331 "),
    ("FR", "FR76 3000 6000 0112 "),
    ("ES", "ES91 2100 0418 4502 "),
]

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

TYPE_VOCABULARY = {
    "invoice": [
        "TAX INVOICE / FACTURA COMERCIAL",
        "Invoice Number: INV-{doc_id:05d}",
        "Billing Terms: Net 30 Days from date of issuance",
        "Item Description: Enterprise consulting and software licenses",
        "Line Item Subtotal: {amount_str}",
        "Applicable Value Added Tax (VAT 20%): Included",
        "Total Amount Due for Payment: {amount_str}",
        "Please remit funds directly to Account IBAN: {iban}",
        "Payment Reference: REF-INV-{doc_id:05d}",
    ],
    "purchase_order": [
        "OFFICIAL PURCHASE ORDER / ORDEN DE COMPRA",
        "Purchase Order Reference: PO-{doc_id:05d}",
        "Procurement Vendor: {correspondent}",
        "Shipping Address: Logistics Dock 4, Industrial Park East",
        "Requested Delivery Date: {date_str}",
        "Authorized Quantities and Line Specifications:",
        "Total Authorized Purchase Budget: {amount_str}",
        "Vendor Billing IBAN: {iban}",
        "Approved by Corporate Purchasing Director",
    ],
    "bank_statement": [
        "MONTHLY ACCOUNT STATEMENT / EXTRACTO BANCARIO",
        "Financial Institution: {correspondent}",
        "Account Holder: Enterprise Operations Group LLC",
        "International Bank Account Number (IBAN): {iban}",
        "Statement Period Closing Date: {date_str}",
        "Previous Ledger Opening Balance: {amount_str}",
        "Summary of Debits, Credits and Wire Transfers",
        "Current Cleared Account Balance: {amount_str}",
        "Branch Clearing Code: 40-02-18 / BIC: GLOBUS33",
    ],
    "utility_bill": [
        "COMMERCIAL UTILITY STATEMENT / FACTURA DE SERVICIOS",
        "Utility Provider: {correspondent}",
        "Service Account Identifier: UTIL-{doc_id:05d}",
        "Metering Cycle: Electricity, Water and Natural Gas",
        "Meter Consumption Reading Period Ending: {date_str}",
        "Recorded Consumption: 4,820 kWh / Rate Tier: Commercial Standard",
        "Total Current Utility Charges Payable: {amount_str}",
        "Direct Debit Mandate Scheduled on IBAN: {iban}",
        "Notice: Emergency services helpline operating 24/7",
    ],
    "letter": [
        "FORMAL BUSINESS CORRESPONDENCE / COMUNICADO OFICIAL",
        "Sender Entity: {correspondent}",
        "Communication Reference Code: LTR-{doc_id:05d}",
        "Date of Notification: {date_str}",
        "Subject: Formal Notice Regarding Commercial Terms and Service Level Agreement",
        "Dear Sir or Madam,",
        "We are writing to formally confirm the operational arrangements and terms.",
        "Please record this formal notification in your corporate records.",
        "Operational Escrow Account for Reference: {iban}",
        "Sincerely yours, Department of Corporate Governance.",
    ],
}


class DocumentMeta(NamedTuple):
    filename: str
    doc_type: str
    correspondent: str
    expected_outcome: str


def format_date(rng: random.Random) -> str:
    """Generate date string in one of 3 realistic formats."""
    year = rng.randint(2024, 2026)
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    fmt_choice = rng.randint(1, 3)
    if fmt_choice == 1:
        # Format 1: YYYY-MM-DD
        return f"{year:04d}-{month:02d}-{day:02d}"
    elif fmt_choice == 2:
        # Format 2: DD/MM/YYYY
        return f"{day:02d}/{month:02d}/{year:04d}"
    else:
        # Format 3: Month DD, YYYY
        return f"{MONTH_NAMES[month - 1]} {day:02d}, {year:04d}"


def format_amount(rng: random.Random) -> str:
    """Generate amount with comma or dot decimal notation."""
    whole = rng.randint(100, 25000)
    cents = rng.randint(0, 99)
    if rng.choice([True, False]):
        # Standard US/UK: 1,450.50
        return f"${whole:,}.{cents:02d}"
    else:
        # European format: 1.450,50
        formatted_whole = f"{whole:,}".replace(",", ".")
        return f"EUR {formatted_whole},{cents:02d}"


def format_iban(rng: random.Random) -> str:
    """Generate realistic IBAN-like account string."""
    _, prefix = rng.choice(IBAN_PREFIXES)
    suffix = f"{rng.randint(1000, 9999)} {rng.randint(10, 99)}"
    return f"{prefix}{suffix}"


def create_pdf_bytes(
    doc_id: int,
    doc_type: str,
    correspondent: str,
    date_str: str,
    amount_str: str,
    iban: str,
    unique_token: str,
) -> bytes:
    """Create deterministic text-layer PDF using fpdf2."""
    pdf = FPDF()
    # Pin creation date for byte determinism
    pdf.creation_date = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Header
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(180, 10, text=correspondent.upper(), new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(3)

    pdf.set_font("helvetica", "B", 12)
    pdf.cell(180, 8, text=f"Document Type: {doc_type.replace('_', ' ').title()}", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("helvetica", "", 10)
    pdf.cell(180, 6, text=f"Date: {date_str}  |  Doc ID: DOC-{doc_id:05d}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(180, 6, text=f"Unique Verification Token: {unique_token}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Body lines with type vocabulary
    lines = TYPE_VOCABULARY[doc_type]
    pdf.set_font("helvetica", "", 10)
    for line in lines:
        rendered = line.format(
            doc_id=doc_id,
            correspondent=correspondent,
            date_str=date_str,
            amount_str=amount_str,
            iban=iban,
        )
        pdf.multi_cell(180, 6, text=rendered, new_x="LMARGIN", new_y="NEXT")

    # Footer note
    pdf.ln(10)
    pdf.set_font("helvetica", "I", 8)
    pdf.cell(180, 5, text="Generated synthetic test artifact for document intake pipeline.", new_x="LMARGIN", new_y="NEXT", align="C")

    return bytes(pdf.output())


def generate_corpus(
    seed: int = 42,
    count: int = 600,
    output_dir: Path | str = "corpus/generated",
    labels_file: Path | str = "corpus/labels.csv",
    manifest_file: Path | str = "corpus/manifest.sha256",
    corrupt_ratio: float = 0.03,
    duplicate_ratio: float = 0.02,
) -> tuple[Path, Path]:
    """Generate PDFs with specified corrupt and duplicate ratios."""
    rng = random.Random(seed)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    labels_path = Path(labels_file)
    labels_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(manifest_file)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    # Clean previous generated files in out_path
    for existing in out_path.glob("*.pdf"):
        try:
            existing.unlink()
        except OSError:
            pass

    # Determine counts
    num_corrupt = round(count * corrupt_ratio)
    num_duplicates = round(count * duplicate_ratio)
    num_ingest = count - num_corrupt - num_duplicates

    # Distribute document types across total count
    doc_assignments: list[tuple[str, str]] = []
    for i in range(count):
        dt = DOCUMENT_TYPES[i % len(DOCUMENT_TYPES)]
        corr = CORRESPONDENTS[i % len(CORRESPONDENTS)]
        doc_assignments.append((dt, corr))

    # Determine outcomes deterministically: assign outcome per index
    # We want valid documents generated first so duplicates can copy valid documents
    outcomes: list[str] = (
        ["ingest"] * num_ingest +
        ["corrupt"] * num_corrupt +
        ["duplicate"] * num_duplicates
    )
    # Shuffle outcomes with seed-derived rng
    rng.shuffle(outcomes)

    generated_valid_bytes: list[bytes] = []
    records: list[DocumentMeta] = []
    hashes: dict[str, str] = {}

    for i in range(count):
        filename = f"doc_{i+1:04d}.pdf"
        filepath = out_path / filename
        doc_type, correspondent = doc_assignments[i]
        outcome = outcomes[i]

        date_str = format_date(rng)
        amount_str = format_amount(rng)
        iban = format_iban(rng)
        unique_token = f"TOKEN-S{seed}-{i+1:04d}-{rng.randint(100000, 999999)}"

        if outcome == "ingest":
            pdf_bytes = create_pdf_bytes(
                doc_id=i + 1,
                doc_type=doc_type,
                correspondent=correspondent,
                date_str=date_str,
                amount_str=amount_str,
                iban=iban,
                unique_token=unique_token,
            )
            generated_valid_bytes.append(pdf_bytes)
            filepath.write_bytes(pdf_bytes)

        elif outcome == "corrupt":
            # Truncated corrupt PDF: take valid PDF header and truncate to 80 bytes
            valid_bytes = create_pdf_bytes(
                doc_id=i + 1,
                doc_type=doc_type,
                correspondent=correspondent,
                date_str=date_str,
                amount_str=amount_str,
                iban=iban,
                unique_token=unique_token,
            )
            corrupt_bytes = valid_bytes[:80] + b"\n%%EOF-TRUNCATED-CORRUPT\n"
            filepath.write_bytes(corrupt_bytes)

        elif outcome == "duplicate":
            # Exact byte-for-byte duplicate of an existing valid file
            if generated_valid_bytes:
                dup_bytes = rng.choice(generated_valid_bytes)
            else:
                dup_bytes = create_pdf_bytes(
                    doc_id=1,
                    doc_type=doc_type,
                    correspondent=correspondent,
                    date_str=date_str,
                    amount_str=amount_str,
                    iban=iban,
                    unique_token=unique_token,
                )
            filepath.write_bytes(dup_bytes)

        sha = hashlib.sha256(filepath.read_bytes()).hexdigest()
        hashes[filename] = sha
        records.append(
            DocumentMeta(
                filename=filename,
                doc_type=doc_type,
                correspondent=correspondent,
                expected_outcome=outcome,
            )
        )

    # Write labels.csv
    with open(labels_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file", "type", "correspondent", "expected_outcome"])
        for r in records:
            writer.writerow([r.filename, r.doc_type, r.correspondent, r.expected_outcome])

    # Write manifest.sha256
    with open(manifest_path, mode="w", encoding="utf-8") as f:
        f.writelines(f"{hashes[fname]}  {fname}\n" for fname in sorted(hashes.keys()))

    return labels_path, manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic PDF corpus for Paperless-ngx")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--count", type=int, default=600, help="Document count (default: 600)")
    parser.add_argument("--output-dir", type=str, default="corpus/generated", help="Output directory")
    parser.add_argument("--labels", type=str, default="corpus/labels.csv", help="Labels CSV path")
    parser.add_argument("--manifest", type=str, default="corpus/manifest.sha256", help="Manifest path")

    args = parser.parse_args()
    labels, manifest = generate_corpus(
        seed=args.seed,
        count=args.count,
        output_dir=args.output_dir,
        labels_file=args.labels,
        manifest_file=args.manifest,
    )
    print(f"Generated {args.count} corpus PDFs with seed {args.seed}.")
    print(f"Labels written to: {labels}")
    print(f"Manifest written to: {manifest}")
    return 0


if __name__ == "__main__":
    main()
