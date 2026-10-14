"""FastAPI API endpoints for SEO & AEO audit."""

import tempfile

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from app.audit import run_full_audit
from app.reporting.pdf import generate_pdf_from_html

app = FastAPI(
    title="SEO & AEO Audit API",
    version="1.0.0",
    description="Automated SEO and Answer Engine Optimization (AEO) audit service for clients.",
)


class AuditRequest(BaseModel):
    """Audit request payload."""

    url: str = Field(..., description="Target website URL to audit (http or https)")
    max_pages: int = Field(default=10, ge=1, le=50, description="Max pages to crawl from same domain")
    allow_local: bool = Field(default=False, description="Allow auditing localhost and private IP addresses")
    run_lighthouse: bool = Field(default=True, description="Execute headless Lighthouse audit on home page")
    lang: str = Field(default="es", description="Language of the report ('es' or 'en')")


@app.get("/health")
def health_check() -> dict[str, str]:
    """Service health check endpoint."""
    return {"status": "ok", "service": "seo-aeo-audit"}


@app.post("/audit")
async def create_audit(req: AuditRequest) -> dict:
    """Run full audit and return structured JSON result."""
    try:
        report = await run_full_audit(
            url=req.url,
            max_pages=req.max_pages,
            allow_local=req.allow_local,
            run_lighthouse=req.run_lighthouse,
            lang=req.lang,
        )
        return {
            "status": "success",
            "target_url": report["target_url"],
            "date": report["date"],
            "overall_score": report["overall_score"],
            "seo_score": report["seo_score"],
            "aeo_score": report["aeo_score"],
            "lighthouse": report["lighthouse"],
            "executive_summary": report["executive_summary"],
            "summary_source": report["summary_source"],
            "issues_count": report["issues_count"],
            "issues": report["issues"],
            "good_points": report["good_points"],
            "pages_analyzed": report["pages_analyzed"],
        }
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err)) from val_err
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error durante la auditoría: {exc}") from exc


@app.post("/audit/html", response_class=HTMLResponse)
async def create_audit_html(req: AuditRequest) -> HTMLResponse:
    """Run full audit and return the rendered HTML report."""
    try:
        report = await run_full_audit(
            url=req.url,
            max_pages=req.max_pages,
            allow_local=req.allow_local,
            run_lighthouse=req.run_lighthouse,
            lang=req.lang,
        )
        return HTMLResponse(content=report["html_report"], status_code=200)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err)) from val_err
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error durante la auditoría: {exc}") from exc


@app.post("/audit/pdf")
async def create_audit_pdf(req: AuditRequest) -> Response:
    """Run full audit and return the PDF report as a downloadable file."""
    try:
        report = await run_full_audit(
            url=req.url,
            max_pages=req.max_pages,
            allow_local=req.allow_local,
            run_lighthouse=req.run_lighthouse,
            lang=req.lang,
        )
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_pdf_path = tmp.name

        generate_pdf_from_html(report["html_report"], tmp_pdf_path)

        with open(tmp_pdf_path, "rb") as f:
            pdf_bytes = f.read()

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=auditoria-seo-aeo.pdf"},
        )
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err)) from val_err
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error generando PDF: {exc}") from exc
