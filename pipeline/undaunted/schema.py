"""
Schema definitions for the Undaunted Knowledge System.

This module defines Pydantic models for all entities and data structures
in the registry. These models serve as the contract between YAML registry
files and the JSON build output.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional, List, Dict, Any
from datetime import date


# Type definitions
EntityType = Literal["person", "place", "event", "concept", "quote", "time"]


class Entity(BaseModel):
    """Base entity model - all entities share these fields."""

    id: str = Field(
        pattern=r"^(person|place|event|concept|quote|time)\.[a-z0-9_]+$",
        description="Unique entity identifier in format 'type.name'",
    )
    type: EntityType
    primary_name: str
    aliases: List[str] = Field(default_factory=list)
    description: str = ""

    @field_validator("aliases")
    @classmethod
    def no_empty_aliases(cls, v: List[str]) -> List[str]:
        """Reject empty or whitespace-only aliases."""
        for alias in v:
            if not alias or alias.strip() == "":
                raise ValueError(f"Alias cannot be empty or whitespace: '{alias}'")
        return v

    @field_validator("aliases")
    @classmethod
    def no_short_aliases(cls, v: List[str]) -> List[str]:
        """Reject aliases of 1-2 characters (too ambiguous)."""
        for alias in v:
            if len(alias.strip()) <= 2:
                raise ValueError(f"Alias too short (must be 3+ chars): '{alias}'")
        return v

    @field_validator("primary_name")
    @classmethod
    def primary_name_not_empty(cls, v: str) -> str:
        """Ensure primary_name is not empty."""
        if not v or v.strip() == "":
            raise ValueError("primary_name cannot be empty")
        return v


class Person(Entity):
    """A person - rabbi, shliach, public figure, etc."""

    type: Literal["person"] = "person"
    born: Optional[str] = None  # ISO date or year
    died: Optional[str] = None  # ISO date or year
    title: Optional[str] = None  # e.g., "Rabbi", "Mr.", "President"


class Place(Entity):
    """A place - city, country, building, etc."""

    type: Literal["place"] = "place"
    coordinates: Optional[tuple[float, float]] = None  # (lat, lon)
    place_type: Optional[str] = None  # e.g., "city", "country", "building"


class Event(Entity):
    """An event - arrest, journey, meeting, etc."""

    type: Literal["event"] = "event"
    date: Optional[Dict[str, str]] = None  # {gregorian: "1927-07-12", hebrew: "12 Tamuz 5687"}
    place_id: Optional[str] = None  # Reference to a place entity


class Concept(Entity):
    """A concept - idea, movement, organization, etc."""

    type: Literal["concept"] = "concept"


class Quote(Entity):
    """A quote - attributed speech or writing."""

    type: Literal["quote"] = "quote"
    speaker: Optional[str] = None  # Entity ID of who said it
    text: str = ""


class Time(Entity):
    """A temporal reference - year, date, era."""

    type: Literal["time"] = "time"
    year: Optional[int] = None
    date_str: Optional[str] = None  # For non-year dates


class Relationship(BaseModel):
    """A relationship between two entities."""

    from_: str = Field(alias="from", description="Source entity ID")
    rel: str = Field(description="Relationship type")
    to: str = Field(description="Target entity ID")
    citation: Optional[str] = None  # Page reference


class Chapter(BaseModel):
    """A chapter in the book."""

    num: int = Field(ge=0, description="Chapter number (0 = preface)")
    title: str
    first: int = Field(description="First PDF page (1-indexed)")
    last: int = Field(description="Last PDF page (1-indexed)")


class Citation(BaseModel):
    """A citation reference in a wiki entry."""

    page: int = Field(description="Book page number (not PDF page)")
    label: str = Field(description="Human-readable label like 'p. 17'")


class WikiParagraph(BaseModel):
    """A paragraph in a wiki section with inline citations."""

    text: str
    citations: List[Citation] = Field(default_factory=list)


class WikiSection(BaseModel):
    """A section in a wiki entry."""

    heading: str
    paragraphs: List[WikiParagraph] = Field(default_factory=list)


class WikiEntry(BaseModel):
    """A complete wiki entry for an entity."""

    entity_id: str = Field(description="The entity this wiki is about")
    title: str
    subtitle: Optional[str] = None
    sections: List[WikiSection] = Field(default_factory=list)


class TagSpan(BaseModel):
    """A tagged span of text in a page."""

    start: int = Field(description="Character offset (0-indexed)")
    end: int = Field(description="Character offset (exclusive)")
    entity_id: Optional[str] = Field(
        default=None, description="Resolved entity ID, or null for unresolved"
    )
    tag_type: EntityType


class Page(BaseModel):
    """A single page from the book with tagged entities."""

    pdf_page: int = Field(description="PDF page number (1-indexed)")
    book_page: int = Field(description="Book page number (1-indexed)")
    chapter: int = Field(description="Chapter number")
    text: str
    tags: List[TagSpan] = Field(default_factory=list)


class Manifest(BaseModel):
    """Build manifest - metadata about the generated site."""

    version: str = Field(description="Build version/timestamp")
    git_sha: Optional[str] = None
    page_range: tuple[int, int] = Field(description="(first_pdf_page, last_pdf_page)")
    entity_count: int
    wiki_ids: List[str] = Field(default_factory=list)


# Registry container
class Registry(BaseModel):
    """The complete registry - all entities, relationships, and chapters."""

    people: List[Person] = Field(default_factory=list)
    places: List[Place] = Field(default_factory=list)
    events: List[Event] = Field(default_factory=list)
    concepts: List[Concept] = Field(default_factory=list)
    quotes: List[Quote] = Field(default_factory=list)
    times: List[Time] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)
    chapters: List[Chapter] = Field(default_factory=list)
    wiki: List[WikiEntry] = Field(default_factory=list)

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get an entity by ID."""
        prefix = entity_id.split(".", 1)[0]
        container_map = {
            "person": self.people,
            "place": self.places,
            "event": self.events,
            "concept": self.concepts,
            "quote": self.quotes,
            "time": self.times,
        }
        container = container_map.get(prefix)
        if container:
            for entity in container:
                if entity.id == entity_id:
                    return entity
        return None

    def all_entities(self) -> List[Entity]:
        """Get all entities as a flat list."""
        result: List[Entity] = []
        result.extend(self.people)
        result.extend(self.places)
        result.extend(self.events)
        result.extend(self.concepts)
        result.extend(self.quotes)
        result.extend(self.times)
        return result

    def get_alias_map(self) -> Dict[str, str]:
        """Build a map of all aliases to entity IDs."""
        alias_map: Dict[str, str] = {}
        for entity in self.all_entities():
            # Add primary name
            if entity.primary_name:
                alias_map[entity.primary_name] = entity.id
            # Add all aliases
            for alias in entity.aliases:
                alias_map[alias] = entity.id
        return alias_map
