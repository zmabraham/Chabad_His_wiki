"""Build the site - generate JSON files from registry."""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from .load import load_registry
from .schema import Registry, Entity


def build_json(
    registry: Registry, output_dir: Path, include_corpus: bool = False
) -> Dict[str, Any]:
    """Build JSON files from registry."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate manifest
    manifest = {
        "version": datetime.now().strftime("%Y-%m-%d-%H%M"),
        "git_sha": None,  # Would be filled by CI
        "page_range": [19, 381],  # From spec
        "entity_count": len(registry.all_entities()),
        "wiki_ids": [w.entity_id for w in registry.wiki],
    }

    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # Convert entities to JSON-serializable format
    entities_data = []
    for entity in registry.all_entities():
        entity_dict = {
            "id": entity.id,
            "type": entity.type,
            "primary_name": entity.primary_name,
            "aliases": entity.aliases,
            "description": entity.description,
        }
        # Add type-specific fields
        if hasattr(entity, "born") and entity.born:
            entity_dict["born"] = entity.born
        if hasattr(entity, "died") and entity.died:
            entity_dict["died"] = entity.died
        entities_data.append(entity_dict)

    (output_dir / "entities.json").write_text(
        json.dumps(entities_data, indent=2, ensure_ascii=False)
    )

    # Relationships
    relationships_data = [
        {"from": rel.from_, "rel": rel.rel, "to": rel.to} for rel in registry.relationships
    ]
    (output_dir / "relationships.json").write_text(json.dumps(relationships_data, indent=2))

    # Chapters
    chapters_data = [
        {"num": ch.num, "title": ch.title, "first": ch.first, "last": ch.last}
        for ch in registry.chapters
    ]
    (output_dir / "chapters.json").write_text(json.dumps(chapters_data, indent=2))

    # Wiki entries (individual files)
    wiki_dir = output_dir / "wiki"
    wiki_dir.mkdir(exist_ok=True)

    for wiki_entry in registry.wiki:
        wiki_data = {
            "entity_id": wiki_entry.entity_id,
            "title": wiki_entry.title,
            "subtitle": wiki_entry.subtitle,
            "sections": [
                {
                    "heading": s.heading,
                    "paragraphs": [
                        {
                            "text": p.text,
                            "citations": [{"page": c.page, "label": c.label} for c in p.citations],
                        }
                        for p in s.paragraphs
                    ],
                }
                for s in wiki_entry.sections
            ],
        }
        (wiki_dir / f"{wiki_entry.entity_id}.json").write_text(
            json.dumps(wiki_data, indent=2, ensure_ascii=False)
        )

    return manifest


def main():
    """CLI entry point for build."""
    import sys
    from ..cli import build as click_build

    # This is called by the CLI
    click_build()
