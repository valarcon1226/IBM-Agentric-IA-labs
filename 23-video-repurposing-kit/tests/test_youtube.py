"""Pruebas unitarias para kit/youtube.py."""


from kit.youtube import format_youtube_time, generate_youtube_package


def test_format_youtube_time():
    """Valida formato de marcas de tiempo para YouTube (MM:SS o HH:MM:SS)."""
    assert format_youtube_time(0.0) == "00:00"
    assert format_youtube_time(75.0) == "01:15"
    assert format_youtube_time(3665.0) == "01:01:05"


def test_generate_youtube_package(sample_transcript, sample_highlights, tmp_path):
    """Verifica que el paquete de YouTube contenga los 5 componentes requeridos."""
    out_file = tmp_path / "youtube_package.md"
    content = generate_youtube_package(
        transcript=sample_transcript,
        highlights=sample_highlights.highlights,
        output_path=out_file,
        video_topic="Estrategias de Video Viral",
    )

    assert out_file.exists()
    assert len(content) > 200

    # 1. 3 Títulos
    assert "3 Opciones de Títulos" in content
    assert "Opción Directa" in content
    assert "Opción Curiosidad" in content
    assert "Opción Historia" in content

    # 2. Capítulos iniciando obligatoriamente en 00:00
    assert "00:00" in content
    assert "Capítulos con Tiempos" in content

    # 3. Descripción
    assert "Descripción Completa para YouTube" in content
    assert "CAPÍTULOS DEL VIDEO:" in content
    assert "Suscríbete" in content

    # 4. 10 Tags SEO
    assert "10 Tags SEO Recomendados" in content
    assert "Copiar y pegar en YouTube Studio:" in content
    # Comprobar tags en lista
    assert "`estrategia de contenido`" in content
    assert "`reutilizacion de video`" in content
