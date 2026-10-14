"""Pruebas unitarias para kit/downloader.py."""

from unittest.mock import MagicMock, patch

from kit.downloader import download_youtube_video, is_youtube_url


def test_is_youtube_url():
    """Valida reconocimiento de URLs válidas e inválidas de YouTube."""
    assert is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert is_youtube_url("https://youtu.be/dQw4w9WgXcQ")
    assert is_youtube_url("http://youtube.com/watch?v=12345")
    assert not is_youtube_url("video.mp4")
    assert not is_youtube_url("C:/videos/podcast.mov")
    assert not is_youtube_url("https://vimeo.com/12345")
    assert not is_youtube_url("")


def test_download_youtube_video_mock(tmp_path, capsys):
    """Verifica que download_youtube_video muestre el aviso legal y llame a yt-dlp."""
    target_dir = tmp_path / "downloads"

    # Mock de yt-dlp
    mock_ydl_instance = MagicMock()
    mock_ydl_instance.extract_info.return_value = {"id": "test_id", "title": "Test Video"}
    mock_file = target_dir / "test_id_Test Video.mp4"
    mock_ydl_instance.prepare_filename.return_value = str(mock_file)

    # Crear el archivo simulado para que exista al retornar
    target_dir.mkdir(parents=True, exist_ok=True)
    mock_file.write_text("dummy video content")

    with patch("yt_dlp.YoutubeDL") as mock_ydl_class:
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance

        res = download_youtube_video("https://www.youtube.com/watch?v=test", target_dir)

        # Confirmar que devolvió la ruta esperada
        assert res == mock_file
        assert res.exists()

        # Confirmar aviso legal en stdout
        captured = capsys.readouterr()
        assert "AVISO LEGAL IMPORTANTE" in captured.out
        assert "Creative Commons" in captured.out
