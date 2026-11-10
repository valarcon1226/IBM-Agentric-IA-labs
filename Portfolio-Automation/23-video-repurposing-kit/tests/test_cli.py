"""Pruebas funcionales de la CLI de kit."""

from unittest.mock import patch

from kit.cli import main


def test_cli_help(capsys):
    """Verifica que el comando de ayuda responda correctamente."""
    code = main(["--help"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Kit de reutilización de video" in captured.out


def test_cli_run_e2e(test_video_path, sample_transcript, tmp_path):
    """
    Verifica una ejecución de extremo a extremo del CLI sobre el video de prueba,
    simulando la transcripción para agilidad de tests.
    """
    out_dir = tmp_path / "cli_output"

    # Patch de transcripción para usar sample_transcript de 120s
    with patch("kit.cli.transcribe_audio", return_value=sample_transcript):
        code = main([
            "run",
            str(test_video_path),
            "--output-dir",
            str(out_dir),
            "--no-llm",
        ])

        assert code == 0

        # Verificar existencia de todos los entregables
        assert (out_dir / "transcript.json").exists()
        assert (out_dir / "transcript.srt").exists()
        assert (out_dir / "highlights.json").exists()
        assert (out_dir / "youtube_package.md").exists()

        clips = list((out_dir / "clips").glob("*.mp4"))
        assert len(clips) >= 2
        for clip in clips:
            assert clip.stat().st_size > 0


def test_cli_render_subcommand(test_video_path, sample_transcript, sample_highlights, tmp_path):
    """Verifica el subcomando `render` usando un highlights.json editado."""
    h_file = tmp_path / "highlights.json"
    h_file.write_text(sample_highlights.model_dump_json(), encoding="utf-8")

    t_file = tmp_path / "transcript.json"
    t_file.write_text(sample_transcript.model_dump_json(), encoding="utf-8")

    clips_out = tmp_path / "custom_clips"

    code = main([
        "render",
        str(test_video_path),
        str(h_file),
        "--transcript",
        str(t_file),
        "--output-dir",
        str(clips_out),
    ])

    assert code == 0
    clips = list(clips_out.glob("*.mp4"))
    assert len(clips) == len(sample_highlights.highlights)
