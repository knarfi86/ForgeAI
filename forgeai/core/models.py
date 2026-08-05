"""Shared domain models for the local workspace."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ProjectMode(str, Enum):
    READ_ONLY = "READ_ONLY"
    PROPOSE = "PROPOSE"
    WRITE_WITH_CONFIRMATION = "WRITE_WITH_CONFIRMATION"
    AUTO_WRITE = "AUTO_WRITE"


class TaskStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    DONE = "DONE"


@dataclass(frozen=True)
class IndexedFile:
    """A text file discovered while indexing a project."""

    path: Path
    relative_path: str
    file_type: str
    size_bytes: int
    modified_at: str
    sha256: str


@dataclass(frozen=True)
class ProjectStatistics:
    """Aggregated information for a project index."""

    file_count: int
    folder_count: int
    file_types: dict[str, int]
