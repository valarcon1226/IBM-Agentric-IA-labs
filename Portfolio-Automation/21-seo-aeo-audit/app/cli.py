"""Command-line interface for running automated SEO and AEO audits."""

import argparse
import asyncio
import os
import sys

from app.audit import run_full_audit


def build_parser() -> argparse.ArgumentParser:
    """Configure CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Auditoría SEO & AEO Automática para Prospección y Clientes."
    )
    parser.add_argument("url", help="URL del sitio web a auditar (ej. https://ejemplo.com)")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=10,
        help="Número máximo de páginas a rastrear del mismo dominio (defecto: 10)",
    )
    parser.add_argument(
        "--allow-local",
        action="store_true",
        help="Permitir auditoría en localhost e IPs privadas para pruebas de desarrollo",
    )
    parser.add_argument(
        "--skip-lighthouse",
        action="store_true",
        help="Omitir auditoría Lighthouse de rendimiento",
    )
    parser.add_argument(
        "--lang",
        choices=["es", "en"],
        default="es",
        help="Idioma del informe generado (defecto: es)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Ruta donde guardar el informe HTML (ej. samples/informe.html)",
    )
    parser.add_argument(
        "--pdf",
        default=None,
        help="Ruta donde exportar el informe en PDF (ej. samples/informe.pdf)",
    )
    return parser


def main() -> None:
    """CLI execution entrypoint."""
    parser = build_parser()
    args = parser.parse_args()

    print(f"\n[INFO] Iniciando auditoria SEO & AEO para: {args.url}")
    print(f"[CONFIG] max_pages={args.max_pages}, allow_local={args.allow_local}, lang={args.lang}")

    try:
        report = asyncio.run(
            run_full_audit(
                url=args.url,
                max_pages=args.max_pages,
                allow_local=args.allow_local,
                run_lighthouse=not args.skip_lighthouse,
                lang=args.lang,
                pdf_output_path=args.pdf,
            )
        )

        print("\n" + "=" * 60)
        print("          RESUMEN DE AUDITORIA SEO & AEO")
        print("=" * 60)
        print(f"  URL Auditada:       {report['target_url']}")
        print(f"  Paginas Analizadas: {report['pages_analyzed']}")
        print(f"  Puntaje Global:     {report['overall_score']} / 100")
        print(f"  Puntaje SEO:        {report['seo_score']} / 100")
        print(f"  Puntaje AEO (IA):   {report['aeo_score']} / 100")

        lh = report["lighthouse"]
        if lh.get("available"):
            print(f"  Lighthouse Perf:    {lh['performance']} / 100")
            print(f"  Lighthouse A11y:    {lh['accessibility']} / 100")
            print(f"  Lighthouse BP:      {lh['best_practices']} / 100")
            print(f"  Lighthouse SEO:     {lh['seo']} / 100")
        else:
            print(f"  Lighthouse:         Omitido ({lh.get('reason')})")

        print("-" * 60)
        print(f"  Total Oportunidades de Mejora: {report['issues_count']}")
        crit = sum(1 for i in report["issues"] if i.get("severity") in ("CRITICAL", "HIGH"))
        med = sum(1 for i in report["issues"] if i.get("severity") == "MEDIUM")
        low = sum(1 for i in report["issues"] if i.get("severity") == "LOW")
        print(f"    - Criticas / Altas: {crit}")
        print(f"    - Medias:           {med}")
        print(f"    - Bajas:            {low}")
        print(f"  Fortalezas Detectadas:        {len(report['good_points'])}")
        print("=" * 60)

        # Save HTML if requested
        if args.output:
            out_dir = os.path.dirname(args.output)
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(report["html_report"])
            print(f"[REPORTE HTML] Guardado en: {args.output}")

        if args.pdf:
            print(f"[REPORTE PDF] Exportado en: {args.pdf}")

        print("[OK] Auditoria finalizada exitosamente.\n")

    except ValueError as val_err:
        print(f"\n[ERROR] Error de validacion: {val_err}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"\n[ERROR] Error ejecutando la auditoria: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
