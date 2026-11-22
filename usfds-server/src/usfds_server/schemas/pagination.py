"""Shared cursor pagination and batch owner resolution helpers for API routers."""
import base64
import json
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple, TypeVar
from uuid import UUID

from fastapi import HTTPException, status

from usfds_core.repositories.base_user_repo import IUserRepository
from usfds_server.schemas.base_response import ResourceOwnerDto

T = TypeVar("T")

DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 200


def _encode_cursor(key: str) -> str:
	raw = json.dumps({"id": key}, separators=(",", ":")).encode("utf-8")
	return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> str:
	try:
		padded = cursor + "=" * (-len(cursor) % 4)
		payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
		if not isinstance(payload, dict) or not isinstance(payload.get("id"), str) or not payload["id"]:
			raise ValueError("Missing cursor id")
		return payload["id"]
	except Exception as exc:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Invalid pagination cursor",
		) from exc


def paginate_cursor(
	items: Sequence[T],
	*,
	limit: int,
	cursor: Optional[str],
	key_fn: Callable[[T], object],
) -> Tuple[List[T], Optional[str]]:
	"""Slice an ordered sequence by opaque keyset cursor and return `(page_items, next_cursor)`."""
	start_idx = 0
	if cursor is not None:
		cursor_id = _decode_cursor(cursor)
		matched = next((idx for idx, item in enumerate(items) if str(key_fn(item)) == cursor_id), None)
		if matched is None:
			return [], None
		start_idx = matched + 1

	window = list(items[start_idx : start_idx + limit + 1])
	has_more = len(window) > limit
	page_items = window[:limit]
	next_cursor = _encode_cursor(str(key_fn(page_items[-1]))) if has_more and page_items else None
	return page_items, next_cursor


def resolve_owners(
	user_repo: IUserRepository,
	user_ids: Iterable[Optional[UUID]],
) -> Dict[UUID, ResourceOwnerDto]:
	"""Batch-resolve non-null user IDs into `ResourceOwnerDto` in a single query."""
	ids = [uid for uid in user_ids if uid is not None]
	if not ids:
		return {}
	users = user_repo.get_by_ids(ids)
	return {
		uid: ResourceOwnerDto(
			user_id=user.user_id,
			username=user.username,
			full_name=user.full_name,
		)
		for uid, user in users.items()
	}
