"""
ObsidianExporter: genera notas Markdown compatibles con Obsidian.
MÓDULO NUEVO — no existe en el lab DocChat original.

Para cada documento ingestado, genera:
  - Una nota .md con YAML frontmatter (título, tags, fecha, fuente)
  - Secciones: resumen, temas, entidades, fragmentos destacados
  - Wiki-links a otros documentos relacionados [[doc]]
  - Actualiza un Índice.md con todos los documentos del vault
"""
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from langchain_core.documents import Document
from config.settings import OBSIDIAN_VAULT_PATH

logger = logging.getLogger(__name__)


class ObsidianExporter:
    """
    Genera y mantiene un vault de Obsidian con notas de los documentos ingestados.
    Cada documento genera una nota .md con su resumen, temas y metadatos.
    El vault funciona como una "segunda mente" consultable en Obsidian.
    """

    def __init__(self):
        self.vault_path = Path(OBSIDIAN_VAULT_PATH)
        self.vault_path.mkdir(parents=True, exist_ok=True)
        # Subcarpeta para las notas de documentos
        self.docs_path = self.vault_path / "Documentos"
        self.docs_path.mkdir(exist_ok=True)
        logger.info(f"ObsidianExporter inicializado. Vault en: {self.vault_path}")

    def export_document(
        self,
        metadata: Dict,
        chunks: List[Document],
        source_path: str,
        base_dir: Path = None,
    ) -> Path:
        """
        Genera una nota Obsidian para un documento ingestado.
        Retorna la ruta de la nota generada (preservando subcarpetas si aplica).
        """
        source_p = Path(source_path)
        file_name = source_p.name
        note_name = self._sanitize_filename(metadata.get("title", file_name))
        
        # Determinar subcarpeta basada en la estructura original
        target_dir = self.docs_path
        if base_dir:
            try:
                rel_dir = source_p.parent.relative_to(base_dir)
                target_dir = self.docs_path / rel_dir
                target_dir.mkdir(parents=True, exist_ok=True)
            except ValueError:
                pass  # Si el archivo no está en base_dir, guardar en raíz de Documentos

        note_path = target_dir / f"{note_name}.md"

        # Extraer fragmentos destacados (primeros 3 chunks no vacíos)
        highlights = self._get_highlights(chunks, n=3)

        # Construir el contenido de la nota
        content = self._build_note(metadata, source_path, highlights, note_name)

        # Escribir la nota
        note_path.write_text(content, encoding="utf-8")
        logger.info(f"Nota Obsidian generada: {note_path}")

        # Actualizar el índice del vault
        self._update_index(note_name, metadata, source_path)

        return note_path

    def _build_note(
        self,
        metadata: Dict,
        source_path: str,
        highlights: List[str],
        note_name: str,
    ) -> str:
        """Construye el contenido completo de la nota .md."""
        now = datetime.now()
        tags = metadata.get("tags", [])
        topics = metadata.get("topics", [])
        doc_type = metadata.get("doc_type", "other")
        language = metadata.get("language", "unknown")
        entities = metadata.get("key_entities", {})

        # Formato de tags para YAML frontmatter (Obsidian los usa para filtrar)
        yaml_tags = "\n".join([f"  - {t}" for t in tags]) if tags else "  - sin-tags"

        content = f"""---
title: "{metadata.get('title', note_name)}"
source: "{source_path}"
ingested: "{now.strftime('%Y-%m-%d')}"
ingested_time: "{now.strftime('%H:%M')}"
doc_type: {doc_type}
language: {language}
tags:
{yaml_tags}
---

# {metadata.get('title', note_name)}

> [!NOTE] Fuente
>  `{Path(source_path).name}` — Ingestado el {now.strftime('%d/%m/%Y a las %H:%M')}

---

## 📋 Resumen

{metadata.get('summary', 'No disponible.')}

---

## 🏷️ Temas principales

{self._format_list(topics)}

---

## 🔑 Entidades clave

"""
        # Entidades
        people = entities.get("people", [])
        orgs = entities.get("organizations", [])
        dates = entities.get("dates", [])
        places = entities.get("places", [])

        if people:
            content += f"**👤 Personas:** {', '.join(people)}\n\n"
        if orgs:
            content += f"**🏢 Organizaciones:** {', '.join(orgs)}\n\n"
        if dates:
            content += f"**📅 Fechas:** {', '.join(dates)}\n\n"
        if places:
            content += f"**📍 Lugares:** {', '.join(places)}\n\n"

        if not any([people, orgs, dates, places]):
            content += "_No se detectaron entidades específicas._\n\n"

        content += "---\n\n##  Fragmentos destacados\n\n"

        for i, highlight in enumerate(highlights, 1):
            # Limitar cada fragmento a 400 chars para no saturar la nota
            snippet = highlight[:400] + ("..." if len(highlight) > 400 else "")
            content += f"> **Fragmento {i}**\n> {snippet.replace(chr(10), chr(10) + '> ')}\n\n"

        if not highlights:
            content += "_No se pudieron extraer fragmentos._\n\n"

        content += f"""---

## 🔗 Navegación

[[Índice]] | [[Documentos/]]

---
*Generado automáticamente por DocIngest*
"""
        return content

    def _update_index(self, note_name: str, metadata: Dict, source_path: str):
        """
        Actualiza el archivo Índice.md del vault con el nuevo documento.
        Si no existe, lo crea con encabezado.
        """
        index_path = self.vault_path / "Índice.md"
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        if not index_path.exists():
            index_content = """# 📚 Índice de Documentos — DocIngest

> Vault generado automáticamente. Abre esta carpeta en Obsidian como vault.

| Documento | Tipo | Tags | Fecha |
|---|---|---|---|
"""
        else:
            index_content = index_path.read_text(encoding="utf-8")

        # Agregar fila al índice
        doc_type = metadata.get("doc_type", "other")
        tags_str = ", ".join([f"`{t}`" for t in metadata.get("tags", [])[:3]])
        new_row = f"| [[Documentos/{note_name}\\|{metadata.get('title', note_name)[:50]}]] | {doc_type} | {tags_str} | {now} |\n"

        index_content += new_row
        index_path.write_text(index_content, encoding="utf-8")
        logger.info(f"Índice actualizado: {index_path}")

    def _get_highlights(self, chunks: List[Document], n: int = 3) -> List[str]:
        """Selecciona los N primeros chunks con contenido sustancial."""
        highlights = []
        for chunk in chunks:
            text = chunk.page_content.strip()
            if len(text) > 100:  # Ignorar chunks muy cortos (headers sueltos)
                highlights.append(text)
            if len(highlights) >= n:
                break
        return highlights

    def _sanitize_filename(self, name: str) -> str:
        """Convierte un título en un nombre de archivo válido para Obsidian."""
        # Remover caracteres no permitidos en nombres de archivo
        name = re.sub(r'[<>:"/\\|?*]', "", name)
        name = re.sub(r'\s+', " ", name).strip()
        # Limitar longitud
        return name[:80] if len(name) > 80 else name

    def _format_list(self, items: List[str]) -> str:
        """Formatea una lista Python como lista Markdown."""
        if not items:
            return "_No detectados._"
        return "\n".join([f"- {item}" for item in items])

    def get_vault_stats(self) -> Dict:
        """Retorna estadísticas del vault actual."""
        notes = list(self.docs_path.glob("*.md"))
        return {
            "total_notes": len(notes),
            "vault_path": str(self.vault_path),
            "notes": [n.stem for n in notes],
        }
