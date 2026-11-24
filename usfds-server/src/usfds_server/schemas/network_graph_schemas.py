from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from usfds_core.domain.entities.case import BlacklistEntityType
from usfds_server.schemas.investigation_api_schemas import NonemptyId


class ExpandNodeRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")
	project_id: UUID
	entity_type: BlacklistEntityType
	entity_value: NonemptyId
	existing_node_ids: list[str] = Field(default_factory=list, max_length=500)
	days: int = Field(default=90, ge=1, le=3650)
	entity_types: list[BlacklistEntityType] | None = None
	hide_super_nodes: bool = False
	case_id: UUID | None = None
