from abc import ABC, abstractmethod
import re
from typing import List, Optional, Tuple
from uuid import UUID

from usfds_core.domain.entities.model import ModelVersion

_SIMPLE_VERSION_RE = re.compile(r"^v(\d+)$", re.IGNORECASE)
_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


class DuplicateModelVersionError(ValueError):
    """Raised when saving a ModelVersion whose (model_id, semver) already exists."""


def parse_version_sort_key(semver: Optional[str]) -> Tuple[int, ...]:
    """Return a comparable tuple so v10 > v2 > legacy 1.0.0 > malformed strings."""
    if not semver:
        return (-1,)
    s = semver.strip()
    m_simple = _SIMPLE_VERSION_RE.match(s)
    if m_simple:
        return (1, int(m_simple.group(1)))
    m_semver = _SEMVER_RE.match(s)
    if m_semver:
        return (0, int(m_semver.group(1)), int(m_semver.group(2)), int(m_semver.group(3)))
    return (-1,)


def format_model_version_label(semver: Optional[str]) -> str:
    """Format a model version for display without duplicating a leading 'v'."""
    if not semver:
        return "v1"
    s = semver.strip()
    return s if s.lower().startswith("v") else f"v{s}"


class IModelVersionRepository(ABC):
    """Abstract interface for ModelVersion persistence in Model Registry."""

    @abstractmethod
    def save(self, version: ModelVersion) -> ModelVersion:
        """Persist or update a ModelVersion."""
        pass

    @abstractmethod
    def get_by_id(self, version_id: UUID) -> Optional[ModelVersion]:
        """Retrieve a ModelVersion by its ID."""
        pass

    @abstractmethod
    def get_latest_version(self, model_id: UUID) -> Optional[ModelVersion]:
        """Retrieve the latest ModelVersion for a model (sorted by registered_at/semver)."""
        pass

    @abstractmethod
    def list_by_model(self, model_id: UUID) -> List[ModelVersion]:
        """List all versions for a given model."""
        pass
