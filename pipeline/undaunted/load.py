"""
Registry loader - reads YAML and Markdown files into Registry objects.
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional
import re

from .schema import (
    Registry,
    Person,
    Place,
    Event,
    Concept,
    Quote,
    Time,
    Relationship,
    Chapter,
    WikiEntry,
    WikiSection,
    WikiParagraph,
    Citation,
    Entity,
)


def load_yaml_file(path: Path) -> List[Dict]:
    """Load a YAML file containing multiple documents."""
    documents = []
    with open(path, "r", encoding="utf-8") as f:
        for doc in yaml.safe_load_all(f):
            if doc is not None:
                documents.append(doc)
    return documents


def load_entity_yaml(
    path: Path, entity_class
) -> List:
    """Load a YAML file of entities."""
    documents = load_yaml_file(path)
    entities = []
    for doc in documents:
        # Handle both list-of-dicts (single YAML doc that is a list) and multiple docs
        items = doc if isinstance(doc, list) else [doc]
        for item in items:
            try:
                entities.append(entity_class(**item))
            except Exception as e:
                raise ValueError(f"Error loading entity from {path}: {e}") from e
    return entities


def parse_citation(label: str) -> Citation:
    """Parse a citation label like 'p. 17' or 'p. 41 / PDF p. 59'."""
    # Extract book page number
    match = re.search(r"p\.?\s*(\d+)", label)
    if match:
        page = int(match.group(1))
    else:
        page = 0

    return Citation(page=page, label=label)


def parse_markdown_wiki(content: str, entity_id: str) -> WikiEntry:
    """Parse a wiki markdown file with frontmatter."""
    # Split frontmatter from content
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Wiki entry for {entity_id} missing frontmatter")

    frontmatter = yaml.safe_load(parts[1])
    body = parts[2].strip()

    title = frontmatter.get("title", "")
    subtitle = frontmatter.get("subtitle")

    sections: List[WikiSection] = []
    current_section: Optional[WikiSection] = None

    for line in body.split("\n"):
        line = line.rstrip()

        # Check for section heading
        if line.startswith("## "):
            if current_section:
                sections.append(current_section)
            current_section = WikiSection(heading=line[3:])

        # Check for footnote/citation
        elif line.startswith("[^") and ":" in line:
            if not current_section:
                current_section = WikiSection(heading="Introduction")
            # This is a citation definition
            # For now, we'll just track it - actual parsing happens when paragraphs reference it
            pass

        # Regular text line
        elif line.strip():
            if not current_section:
                current_section = WikiSection(heading="Introduction")
            # Add to current paragraph or start new one
            if not current_section.paragraphs:
                current_section.paragraphs.append(WikiParagraph(text=line))
            else:
                # Append to existing paragraph if it looks like continuation
                last = current_section.paragraphs[-1]
                last.text += "\n" + line

    if current_section:
        sections.append(current_section)

    return WikiEntry(entity_id=entity_id, title=title, subtitle=subtitle, sections=sections)


def load_registry(registry_dir: Path) -> Registry:
    """Load the complete registry from YAML files."""
    registry = Registry()

    # Load entities by type
    entity_types = {
        "people.yaml": Person,
        "places.yaml": Place,
        "events.yaml": Event,
        "concepts.yaml": Concept,
        "quotes.yaml": Quote,
        "times.yaml": Time,
    }

    for filename, entity_class in entity_types.items():
        path = registry_dir / filename
        if path.exists():
            entities = load_entity_yaml(path, entity_class)
            if entity_class == Person:
                registry.people = entities  # type: ignore
            elif entity_class == Place:
                registry.places = entities  # type: ignore
            elif entity_class == Event:
                registry.events = entities  # type: ignore
            elif entity_class == Concept:
                registry.concepts = entities  # type: ignore
            elif entity_class == Quote:
                registry.quotes = entities  # type: ignore
            elif entity_class == Time:
                registry.times = entities  # type: ignore

    # Load relationships
    relationships_path = registry_dir / "relationships.yaml"
    if relationships_path.exists():
        docs = load_yaml_file(relationships_path)
        registry.relationships = [Relationship(**doc) for doc in docs]

    # Load chapters
    chapters_path = registry_dir / "chapters.yaml"
    if chapters_path.exists():
        docs = load_yaml_file(chapters_path)
        registry.chapters = [Chapter(**doc) for doc in docs]

    # Load wiki entries
    wiki_dir = registry_dir / "wiki"
    if wiki_dir.exists():
        wiki_entries: List[WikiEntry] = []
        for md_file in wiki_dir.glob("*.md"):
            entity_id = md_file.stem
            content = md_file.read_text(encoding="utf-8")
            try:
                entry = parse_markdown_wiki(content, entity_id)
                wiki_entries.append(entry)
            except Exception as e:
                raise ValueError(f"Error loading wiki entry {md_file}: {e}") from e
        registry.wiki = wiki_entries

    return registry
