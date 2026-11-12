"""Pruebas funcionales de los endpoints de la interfaz web en kit/web.py."""

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from kit.moments import HighlightSegment
from kit.web import app

client = TestClient(app)


def test_web_index_page():
    """Verifica que la página principal cargue con la UI y aviso legal."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Video Repurposing Kit" in resp.text
    assert "Aviso de Uso Responsable" in resp.text
    assert "Momentos Virales" in resp.text


def test_web_process_and_render_flow(test_video_path, sample_transcript, tmp_path):
    """Verifica el flujo de carga, procesamiento y renderizado vía API web."""
    # Simular transcripción para velocidad de tests
    with patch("kit.web.transcribe_audio", return_value=sample_transcript):
        # 1. Procesar video
        with open(test_video_path, "rb") as vf:
            resp_proc = client.post(
                "/api/process",
                files={"file": ("test_video.mp4", vf, "video/mp4")},
                data={"no_llm": "true"},
            )

        assert resp_proc.status_code == 200
        proc_data = resp_proc.json()
        assert "highlights" in proc_data
        assert len(proc_data["highlights"]) >= 2

        # 2. Renderizar clips a partir de los momentos
        highlights_to_render = [
            HighlightSegment(
                id=1,
                start=20.0,
                end=45.0,
                duration=25.0,
                title="Clip Web Test",
                hook="Gancho de prueba web",
                score=9.0,
            ).model_dump()
        ]

        resp_render = client.post(
            "/api/render",
            json={"highlights": highlights_to_render},
        )
        assert resp_render.status_code == 200
        render_data = resp_render.json()
        assert len(render_data["clips"]) == 1
        assert "youtube_package_content" in render_data

        # 3. Descarga de clip
        clip_path = Path(render_data["clips"][0])
        resp_dl = client.get(f"/api/download/{clip_path.name}")
        assert resp_dl.status_code == 200
        assert resp_dl.headers["content-type"] == "video/mp4"
