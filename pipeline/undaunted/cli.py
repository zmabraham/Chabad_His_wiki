"""
CLI for the Undaunted build pipeline.
"""

import click
from pathlib import Path
import json

from .load import load_registry
from .validate import validate_registry_dir, ValidationReport


@click.group()
@click.version_option(version="0.1.0")
def main():
    """Undaunted Knowledge System - Build pipeline."""
    pass


@main.command()
@click.argument("registry_dir", type=click.Path(exists=True, path_type=Path), default="registry")
def validate(registry_dir: Path):
    """Validate the registry for errors."""
    click.echo(f"Validating registry at: {registry_dir}")

    report = validate_registry_dir(registry_dir)
    report.print_report()

    # Exit with error code if validation failed
    if report.failed():
        raise click.ClickException("Validation failed")


@main.command()
@click.argument("registry_dir", type=click.Path(exists=True, path_type=Path), default="registry")
@click.option("--output", "-o", type=click.Path(path_type=Path), default="site/public/data")
@click.option("--no-corpus", is_flag=True, help="Build without corpus (registry-only)")
def build(registry_dir: Path, output: Path, no_corpus: bool):
    """Build the site from the registry."""
    click.echo(f"Loading registry from: {registry_dir}")

    # First validate
    report = validate_registry_dir(registry_dir)
    if report.failed():
        click.echo("❌ Validation failed - build aborted")
        report.print_report()
        raise click.ClickException("Cannot build with invalid registry")

    click.echo("✓ Validation passed")

    # Load registry
    registry = load_registry(registry_dir)
    all_entities = registry.all_entities()
    click.echo(f"✓ Loaded {len(all_entities)} entities")

    # Create output directory
    output.mkdir(parents=True, exist_ok=True)

    # Generate manifest
    from datetime import datetime

    manifest = {
        "version": datetime.now().strftime("%Y-%m-%d-%H%M"),
        "page_range": [19, 381],
        "entity_count": len(all_entities),
        "wiki_ids": [w.entity_id for w in registry.wiki],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # Generate entities.json
    entities_data = []
    for entity in all_entities:
        entity_dict = {
            "id": entity.id,
            "type": entity.type,
            "primary_name": entity.primary_name,
            "aliases": entity.aliases,
            "description": entity.description,
        }
        if hasattr(entity, "born") and entity.born:
            entity_dict["born"] = entity.born
        if hasattr(entity, "died") and entity.died:
            entity_dict["died"] = entity.died
        entities_data.append(entity_dict)

    (output / "entities.json").write_text(json.dumps(entities_data, indent=2, ensure_ascii=False))

    # Generate relationships.json
    relationships_data = [
        {"from": rel.from_, "rel": rel.rel, "to": rel.to} for rel in registry.relationships
    ]
    (output / "relationships.json").write_text(json.dumps(relationships_data, indent=2))

    # Generate chapters.json
    chapters_data = [
        {"num": ch.num, "title": ch.title, "first": ch.first, "last": ch.last}
        for ch in registry.chapters
    ]
    (output / "chapters.json").write_text(json.dumps(chapters_data, indent=2))

    # Generate wiki entries
    wiki_dir = output / "wiki"
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

    click.echo(f"✓ Built to: {output}")
    click.echo(f"  - manifest.json")
    click.echo(f"  - entities.json ({len(entities_data)} entities)")
    click.echo(f"  - relationships.json ({len(relationships_data)} relationships)")
    click.echo(f"  - chapters.json ({len(chapters_data)} chapters)")
    click.echo(f"  - wiki/ ({len(registry.wiki)} entries)")

    if no_corpus:
        click.echo("Note: Built in registry-only mode (no corpus)")


if __name__ == "__main__":
    main()
