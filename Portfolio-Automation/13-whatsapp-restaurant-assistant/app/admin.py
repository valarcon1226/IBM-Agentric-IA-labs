import io
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from app.retrieval import KNOWLEDGE_DIR, _load_corpus
from app.security import verify_admin_api_key

router = APIRouter()


@router.get("/admin", response_class=HTMLResponse)
async def get_admin_panel():
    return """
    <html>
        <body>
            <h1>Upload Knowledge</h1>
            <form action="/admin/upload" method="post" enctype="multipart/form-data">
                <input type="file" name="file" accept=".md,.pdf">
                <input type="text" name="token" placeholder="Bearer Token">
                <button type="submit">Upload</button>
            </form>
            <script>
                document.querySelector('form').onsubmit = async (e) => {
                    e.preventDefault();
                    const formData = new FormData(e.target);
                    const token = formData.get('token');
                    formData.delete('token');
                    const res = await fetch('/admin/upload', {
                        method: 'POST',
                        headers: {'Authorization': 'Bearer ' + token},
                        body: formData
                    });
                    alert(await res.text());
                };
            </script>
        </body>
    </html>
    """


@router.post("/admin/upload", dependencies=[Depends(verify_admin_api_key)])
async def upload_knowledge(file: UploadFile = File(...)):
    if not file.filename.endswith((".md", ".pdf")):
        raise HTTPException(400, "Solo archivos .md o .pdf")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(400, "El archivo excede los 5MB")

    path = KNOWLEDGE_DIR / Path(file.filename).name  # strip any directory parts (path traversal)

    if file.filename.endswith(".pdf"):
        try:
            import pypdf

            reader = pypdf.PdfReader(io.BytesIO(content))
            text = "\n\n".join(page.extract_text() for page in reader.pages if page.extract_text())
            path = path.with_suffix(".md")
            path.write_text(text, encoding="utf-8")
        except ImportError as e:
            raise HTTPException(500, "pypdf no está instalado") from e
        except Exception as e:
            raise HTTPException(400, "No se pudo leer el PDF") from e
    else:
        path.write_bytes(content)

    _load_corpus.cache_clear()
    return {"status": "ok", "message": "Archivo subido y base de conocimiento reindexada."}
