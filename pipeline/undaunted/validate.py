"""
Registry validation - checks for common errors and inconsistencies.
"""

from typing import Set, List, Tuple, Optional, Dict
from collections import defaultdict

from .schema import Registry
from .load import load_registry
from pathlib import Path

# Common English stopwords that should not be aliases
STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "as",
    "is",
    "was",
    "are",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "must",
    "shall",
    "can",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "he",
    "him",
    "his",
    "she",
    "her",
    "hers",
    "they",
    "them",
    "their",
    "we",
    "us",
    "our",
    "you",
    "your",
}


class ValidationError:
    """A validation error with location and message."""

    def __init__(self, category: str, message: str, location: str = ""):
        self.category = category
        self.message = message
        self.location = location

    def __str__(self) -> str:
        if self.location:
            return f"[{self.category}] {self.location}: {self.message}"
        return f"[{self.category}] {self.message}"


class ValidationReport:
    """Collection of validation errors."""

    def __init__(self):
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []

    def add_error(self, category: str, message: str, location: str = ""):
        self.errors.append(ValidationError(category, message, location))

    def add_warning(self, category: str, message: str, location: str = ""):
        self.warnings.append(ValidationError(category, message, location))

    def failed(self) -> bool:
        return len(self.errors) > 0

    def print_report(self):
        if not self.errors and not self.warnings:
            print("✓ Validation passed - no errors or warnings")
            return

        if self.errors:
            print(f"\n❌ {len(self.errors)} error(s):")
            for err in self.errors:
                print(f"  {err}")

        if self.warnings:
            print(f"\n⚠ {len(self.warnings)} warning(s):")
            for warn in self.warnings:
                print(f"  {warn}")

        if self.errors:
            print(f"\n❌ Validation FAILED with {len(self.errors)} error(s)")
        else:
            print(f"\n✓ Validation passed with {len(self.warnings)} warning(s)")


def validate_registry(registry: Registry, report: ValidationReport):
    """Run all validation checks on a registry."""

    # Check 1: No duplicate entity IDs
    _check_duplicate_ids(registry, report)

    # Check 2: No alias collisions
    _check_alias_collisions(registry, report)

    # Check 3: All relationship references exist
    _check_relationship_references(registry, report)

    # Check 4: Wiki entries reference real entities
    _check_wiki_entity_references(registry, report)

    # Check 5: Event place_id references exist
    _check_event_place_references(registry, report)

    # Check 6: Quote speaker references exist
    _check_quote_speaker_references(registry, report)

    # Check 7: No alias is a common stopword
    _check_stopword_aliases(registry, report)

    # Check 8: Entity IDs follow the correct pattern
    _check_entity_id_patterns(registry, report)

    return report


def _check_duplicate_ids(registry: Registry, report: ValidationReport):
    """Check that no two entities share the same ID."""
    seen: Set[str] = set()
    duplicates: Set[str] = set()

    for entity in registry.all_entities():
        if entity.id in seen:
            duplicates.add(entity.id)
            report.add_error("duplicate_id", f"Duplicate entity ID: {entity.id}", entity.id)
        seen.add(entity.id)


def _check_alias_collisions(registry: Registry, report: ValidationReport):
    """Check that two entities don't share an alias."""
    alias_to_entities: Dict[str, List[str]] = defaultdict(list)

    for entity in registry.all_entities():
        # Check primary name
        if entity.primary_name:
            alias_to_entities[entity.primary_name].append(entity.id)
        # Check all aliases
        for alias in entity.aliases:
            alias_to_entities[alias].append(entity.id)

    # Find collisions
    for alias, entity_ids in alias_to_entities.items():
        if len(entity_ids) > 1:
            report.add_error(
                "alias_collision",
                f"Alias '{alias}' is used by multiple entities: {', '.join(entity_ids)}",
                f"alias: {alias}",
            )


def _check_relationship_references(registry: Registry, report: ValidationReport):
    """Check that all relationship from/to references exist."""
    all_ids = {e.id for e in registry.all_entities()}

    for rel in registry.relationships:
        if rel.from_ not in all_ids:
            report.add_error(
                "broken_reference",
                f"Relationship references non-existent entity: {rel.from_}",
                f"relationship from={rel.from_} to={rel.to}",
            )
        if rel.to not in all_ids:
            report.add_error(
                "broken_reference",
                f"Relationship references non-existent entity: {rel.to}",
                f"relationship from={rel.from_} to={rel.to}",
            )


def _check_wiki_entity_references(registry: Registry, report: ValidationReport):
    """Check that wiki entries reference real entities."""
    all_ids = {e.id for e in registry.all_entities()}

    for wiki_entry in registry.wiki:
        if wiki_entry.entity_id not in all_ids:
            report.add_error(
                "broken_reference",
                f"Wiki entry references non-existent entity: {wiki_entry.entity_id}",
                f"wiki/{wiki_entry.entity_id}.md",
            )


def _check_event_place_references(registry: Registry, report: ValidationReport):
    """Check that event.place_id references exist."""
    place_ids = {p.id for p in registry.places}

    for event in registry.events:
        if event.place_id and event.place_id not in place_ids:
            report.add_error(
                "broken_reference",
                f"Event references non-existent place: {event.place_id}",
                event.id,
            )


def _check_quote_speaker_references(registry: Registry, report: ValidationReport):
    """Check that quote.speaker references exist."""
    person_ids = {p.id for p in registry.people}

    for quote in registry.quotes:
        if quote.speaker and quote.speaker not in person_ids:
            report.add_error(
                "broken_reference",
                f"Quote references non-existent person: {quote.speaker}",
                quote.id,
            )


def _check_stopword_aliases(registry: Registry, report: ValidationReport):
    """Check that no alias is a common English stopword."""
    for entity in registry.all_entities():
        all_names = [entity.primary_name] + entity.aliases
        for name in all_names:
            if name.lower() in STOPWORDS:
                report.add_error(
                    "stopword_alias", f"Alias is a common stopword: '{name}'", entity.id
                )


def _check_entity_id_patterns(registry: Registry, report: ValidationReport):
    """Check that entity IDs follow the pattern 'type.name'."""
    import re

    pattern = re.compile(r"^(person|place|event|concept|quote|time)\.[a-z0-9_]+$")

    for entity in registry.all_entities():
        if not pattern.match(entity.id):
            report.add_error(
                "invalid_id",
                f"Entity ID doesn't match pattern 'type.name': {entity.id}",
                entity.id,
            )


def validate_registry_dir(registry_dir: Path) -> ValidationReport:
    """Load and validate a registry from a directory."""
    report = ValidationReport()

    try:
        registry = load_registry(registry_dir)
    except Exception as e:
        report.add_error("load_error", f"Failed to load registry: {e}")
        return report

    return validate_registry(registry, report)
