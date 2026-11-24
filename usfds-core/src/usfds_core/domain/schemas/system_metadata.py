"""Single source of truth for canonical system column aliases, resolution, and non-ML exclusion rules."""
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Set, Union

from usfds_core.domain.entities.enums import (
	ColumnCategory,
	ColumnMlRole,
	LogicalDataType,
)
from usfds_core.domain.entities.system_metadata import SystemColumnMetadata

CORE_COLUMN_KEYS: FrozenSet[str] = frozenset(
	{"event_id", "timestamp", "amount", "user_id", "label"}
)

DEFAULT_SYSTEM_COLUMN_ALIASES: Dict[str, List[str]] = {
	"event_id": [
		"event_id",
		"transaction_id",
		"TransactionID",
		"tx_id",
		"trans_id",
		"id",
		"trans_num",
	],
	"timestamp": [
		"timestamp",
		"transaction_time",
		"TransactionDT",
		"tx_time",
		"event_timestamp",
		"time",
		"Time",
		"datetime",
		"date_time",
		"trans_date_time",
		"trans_date_trans_time",
		"created_at",
	],
	"amount": [
		"amount",
		"Amount",
		"transaction_amount",
		"TransactionAmt",
		"tx_amount",
		"amt",
	],
	"user_id": [
		"user_id",
		"customer_id",
		"client_id",
		"account_id",
		"card_id",
		"card1",
		"CLIENTNUM",
		"cc_num",
		"entity_id",
	],
	"label": [
		"label",
		"is_fraud",
		"isFraud",
		"fraud_label",
		"target",
		"fraud",
		"Fraud",
		"Class",
		"class",
	],
}

DEFAULT_SYSTEM_COLUMN_SPECS: List[Dict[str, Any]] = [
	{
		"column_key": "event_id",
		"display_name": "Mã giao dịch",
		"category": ColumnCategory.CORE,
		"logical_type": LogicalDataType.STRING,
		"is_required": True,
		"ml_role": ColumnMlRole.IDENTIFIER,
		"aliases": list(DEFAULT_SYSTEM_COLUMN_ALIASES["event_id"]),
		"description": "Mã định danh duy nhất cho mỗi sự kiện giao dịch",
		"is_active": True,
		"display_order": 1,
	},
	{
		"column_key": "timestamp",
		"display_name": "Thời gian giao dịch",
		"category": ColumnCategory.CORE,
		"logical_type": LogicalDataType.DATETIME,
		"is_required": True,
		"ml_role": ColumnMlRole.TIMESTAMP,
		"aliases": list(DEFAULT_SYSTEM_COLUMN_ALIASES["timestamp"]),
		"description": "Dấu thời gian phát sinh giao dịch (dùng cho chia tập theo thời gian và đặc trưng vận tốc)",
		"is_active": True,
		"display_order": 2,
	},
	{
		"column_key": "amount",
		"display_name": "Số tiền giao dịch",
		"category": ColumnCategory.CORE,
		"logical_type": LogicalDataType.NUMERIC,
		"is_required": True,
		"ml_role": ColumnMlRole.FEATURE,
		"aliases": list(DEFAULT_SYSTEM_COLUMN_ALIASES["amount"]),
		"description": "Giá trị tiền tệ của giao dịch",
		"is_active": True,
		"display_order": 3,
	},
	{
		"column_key": "user_id",
		"display_name": "Mã người dùng / tài khoản",
		"category": ColumnCategory.CORE,
		"logical_type": LogicalDataType.STRING,
		"is_required": True,
		"ml_role": ColumnMlRole.IDENTIFIER,
		"aliases": list(DEFAULT_SYSTEM_COLUMN_ALIASES["user_id"]),
		"description": "Định danh tài khoản, thẻ hoặc khách hàng thực hiện giao dịch",
		"is_active": True,
		"display_order": 4,
	},
	{
		"column_key": "label",
		"display_name": "Nhãn gian lận",
		"category": ColumnCategory.CORE,
		"logical_type": LogicalDataType.NUMERIC,
		"is_required": True,
		"ml_role": ColumnMlRole.LABEL,
		"aliases": list(DEFAULT_SYSTEM_COLUMN_ALIASES["label"]),
		"description": "Nhãn phân loại gian lận (0 = Hợp lệ, 1 = Gian lận)",
		"is_active": True,
		"display_order": 5,
	},
	{
		"column_key": "merchant",
		"display_name": "Đơn vị chấp nhận thẻ (Merchant)",
		"category": ColumnCategory.DOMAIN,
		"logical_type": LogicalDataType.STRING,
		"is_required": False,
		"ml_role": ColumnMlRole.FEATURE,
		"aliases": ["merchant", "merch_name", "merchant_name", "merchant_id"],
		"description": "Tên hoặc mã đơn vị cung cấp dịch vụ/hàng hóa",
		"is_active": True,
		"display_order": 10,
	},
	{
		"column_key": "category",
		"display_name": "Danh mục giao dịch",
		"category": ColumnCategory.DOMAIN,
		"logical_type": LogicalDataType.STRING,
		"is_required": False,
		"ml_role": ColumnMlRole.FEATURE,
		"aliases": ["category", "merchant_category", "mcc"],
		"description": "Nhóm ngành hàng hoặc mã danh mục MCC của giao dịch",
		"is_active": True,
		"display_order": 11,
	},
	{
		"column_key": "device_id",
		"display_name": "Mã thiết bị",
		"category": ColumnCategory.DOMAIN,
		"logical_type": LogicalDataType.STRING,
		"is_required": False,
		"ml_role": ColumnMlRole.IDENTIFIER,
		"aliases": ["device_id", "device", "device_hash", "device_fingerprint", "id_30", "id_31"],
		"description": "Định danh thiết bị đầu cuối thực hiện giao dịch",
		"is_active": True,
		"display_order": 12,
	},
	{
		"column_key": "ip_address",
		"display_name": "Địa chỉ IP",
		"category": ColumnCategory.DOMAIN,
		"logical_type": LogicalDataType.STRING,
		"is_required": False,
		"ml_role": ColumnMlRole.IDENTIFIER,
		"aliases": ["ip_address", "ip", "ip_addr", "client_ip", "source_ip"],
		"description": "Địa chỉ IP nguồn phát sinh giao dịch",
		"is_active": True,
		"display_order": 13,
	},
	{
		"column_key": "email",
		"display_name": "Email tài khoản / thanh toán",
		"category": ColumnCategory.DOMAIN,
		"logical_type": LogicalDataType.STRING,
		"is_required": False,
		"ml_role": ColumnMlRole.IDENTIFIER,
		"aliases": ["email", "email_address", "P_emaildomain", "R_emaildomain", "payer_email"],
		"description": "Địa chỉ email gắn với tài khoản hoặc giao dịch",
		"is_active": True,
		"display_order": 14,
	},
	{
		"column_key": "phone_number",
		"display_name": "Số điện thoại",
		"category": ColumnCategory.DOMAIN,
		"logical_type": LogicalDataType.STRING,
		"is_required": False,
		"ml_role": ColumnMlRole.IDENTIFIER,
		"aliases": ["phone_number", "phone", "mobile", "tel", "contact_phone"],
		"description": "Số điện thoại liên hệ hoặc xác thực OTP",
		"is_active": True,
		"display_order": 15,
	},
	{
		"column_key": "card_id",
		"display_name": "Mã thẻ thanh toán",
		"category": ColumnCategory.DOMAIN,
		"logical_type": LogicalDataType.STRING,
		"is_required": False,
		"ml_role": ColumnMlRole.IDENTIFIER,
		"aliases": ["card_id", "card_token", "cc_num", "card1"],
		"description": "Mã định danh thẻ hoặc token thẻ",
		"is_active": True,
		"display_order": 16,
	},
	{
		"column_key": "card_bin",
		"display_name": "Đầu số thẻ (BIN)",
		"category": ColumnCategory.DOMAIN,
		"logical_type": LogicalDataType.STRING,
		"is_required": False,
		"ml_role": ColumnMlRole.FEATURE,
		"aliases": ["card_bin", "bin", "iin", "card2", "card3", "card6"],
		"description": "6 chữ số đầu nhận diện ngân hàng phát hành và loại thẻ",
		"is_active": True,
		"display_order": 17,
	},
	{
		"column_key": "country",
		"display_name": "Quốc gia giao dịch",
		"category": ColumnCategory.DOMAIN,
		"logical_type": LogicalDataType.STRING,
		"is_required": False,
		"ml_role": ColumnMlRole.FEATURE,
		"aliases": ["country", "ip_country", "geo_country", "billing_country"],
		"description": "Mã quốc gia nơi phát sinh giao dịch",
		"is_active": True,
		"display_order": 18,
	},
	{
		"column_key": "bin_country",
		"display_name": "Quốc gia phát hành thẻ (BIN)",
		"category": ColumnCategory.DOMAIN,
		"logical_type": LogicalDataType.STRING,
		"is_required": False,
		"ml_role": ColumnMlRole.FEATURE,
		"aliases": ["bin_country", "issuer_country", "card_country"],
		"description": "Quốc gia của ngân hàng phát hành thẻ theo mã BIN",
		"is_active": True,
		"display_order": 19,
	},
	{
		"column_key": "currency",
		"display_name": "Đơn vị tiền tệ",
		"category": ColumnCategory.DOMAIN,
		"logical_type": LogicalDataType.STRING,
		"is_required": False,
		"ml_role": ColumnMlRole.FEATURE,
		"aliases": ["currency", "currency_code", "tx_currency"],
		"description": "Mã tiền tệ ISO 4217 của giao dịch",
		"is_active": True,
		"display_order": 20,
	},
	{
		"column_key": "channel",
		"display_name": "Kênh giao dịch",
		"category": ColumnCategory.DOMAIN,
		"logical_type": LogicalDataType.STRING,
		"is_required": False,
		"ml_role": ColumnMlRole.FEATURE,
		"aliases": ["channel", "tx_channel", "entry_mode", "payment_channel"],
		"description": "Kênh thực hiện giao dịch (web, mobile, pos, atm)",
		"is_active": True,
		"display_order": 21,
	},
	{
		"column_key": "lat",
		"display_name": "Vĩ độ chủ thẻ",
		"category": ColumnCategory.DOMAIN,
		"logical_type": LogicalDataType.NUMERIC,
		"is_required": False,
		"ml_role": ColumnMlRole.FEATURE,
		"aliases": ["lat", "latitude", "cust_lat", "user_lat"],
		"description": "Vĩ độ địa lý của khách hàng / thiết bị",
		"is_active": True,
		"display_order": 22,
	},
	{
		"column_key": "long",
		"display_name": "Kinh độ chủ thẻ",
		"category": ColumnCategory.DOMAIN,
		"logical_type": LogicalDataType.NUMERIC,
		"is_required": False,
		"ml_role": ColumnMlRole.FEATURE,
		"aliases": ["long", "lng", "lon", "longitude", "cust_long", "user_long"],
		"description": "Kinh độ địa lý của khách hàng / thiết bị",
		"is_active": True,
		"display_order": 23,
	},
	{
		"column_key": "merch_lat",
		"display_name": "Vĩ độ đơn vị chấp nhận thẻ",
		"category": ColumnCategory.DOMAIN,
		"logical_type": LogicalDataType.NUMERIC,
		"is_required": False,
		"ml_role": ColumnMlRole.FEATURE,
		"aliases": ["merch_lat", "merchant_lat", "shipping_lat"],
		"description": "Vĩ độ địa điểm của merchant / điểm giao hàng",
		"is_active": True,
		"display_order": 24,
	},
	{
		"column_key": "merch_long",
		"display_name": "Kinh độ đơn vị chấp nhận thẻ",
		"category": ColumnCategory.DOMAIN,
		"logical_type": LogicalDataType.NUMERIC,
		"is_required": False,
		"ml_role": ColumnMlRole.FEATURE,
		"aliases": ["merch_long", "merch_lon", "merchant_long", "shipping_long"],
		"description": "Kinh độ địa điểm của merchant / điểm giao hàng",
		"is_active": True,
		"display_order": 25,
	},
	{
		"column_key": "billing_zip",
		"display_name": "Mã bưu chính thanh toán",
		"category": ColumnCategory.DOMAIN,
		"logical_type": LogicalDataType.STRING,
		"is_required": False,
		"ml_role": ColumnMlRole.FEATURE,
		"aliases": ["billing_zip", "zip", "postal_code", "addr1", "shipping_zip"],
		"description": "Mã bưu chính hoặc vùng địa chỉ thanh toán",
		"is_active": True,
		"display_order": 26,
	},
	{
		"column_key": "user_agent",
		"display_name": "User-Agent trình duyệt/ứng dụng",
		"category": ColumnCategory.DOMAIN,
		"logical_type": LogicalDataType.STRING,
		"is_required": False,
		"ml_role": ColumnMlRole.IDENTIFIER,
		"aliases": ["user_agent", "ua", "http_user_agent", "browser_ua"],
		"description": "Chuỗi nhận diện trình duyệt, hệ điều hành hoặc bot",
		"is_active": True,
		"display_order": 27,
	},
]


def build_default_system_columns() -> List[SystemColumnMetadata]:
	"""Creates default in-memory SystemColumnMetadata instances (5 CORE + 2 DOMAIN)."""
	return [
		SystemColumnMetadata(
			column_key=spec["column_key"],
			display_name=spec["display_name"],
			category=spec["category"],
			logical_type=spec["logical_type"],
			is_required=spec["is_required"],
			ml_role=spec["ml_role"],
			aliases=list(spec["aliases"]),
			description=spec["description"],
			is_active=spec["is_active"],
			display_order=spec["display_order"],
		)
		for spec in DEFAULT_SYSTEM_COLUMN_SPECS
	]


def _normalize_col_name(name: str) -> str:
	return str(name).strip().lower().replace("_", "").replace(" ", "").replace("-", "")


def _dedupe_candidates(items: Iterable[str]) -> List[str]:
	seen: Set[str] = set()
	out: List[str] = []
	for item in items:
		cleaned = str(item).strip()
		if not cleaned:
			continue
		key = cleaned.lower()
		if key not in seen:
			seen.add(key)
			out.append(cleaned)
	return out


def resolve_canonical_column(
	columns: Any,
	canonical_key: Union[str, Any],
	requested_col: Optional[str] = None,
	extra_aliases: Optional[Iterable[str]] = None,
	normalized_match: bool = True,
	strict_requested: bool = True,
) -> Optional[str]:
	"""Resolves a canonical column name against a DataFrame or iterable of column names.

	Resolution order:
	1. If `requested_col` is explicitly supplied (and not 'auto'), attempt exact, case-insensitive,
	   then normalized match on `requested_col`.
	2. If not matched directly:
	   - When `strict_requested=True` and `requested_col` was provided (not None/'auto'),
	     only fall back to `canonical_key` aliases if `requested_col` itself belongs to that canonical alias group.
	   - Otherwise search `canonical_key` + `extra_aliases` + `DEFAULT_SYSTEM_COLUMN_ALIASES[canonical_key]`
	     by exact -> case-insensitive -> normalized match.
	"""
	if columns is None:
		return None
	raw_cols = columns.columns if hasattr(columns, "columns") else columns
	col_list = [str(c) for c in raw_cols]
	if not col_list:
		return None

	canonical_str = canonical_key.value if hasattr(canonical_key, "value") else str(canonical_key)
	canonical_lower = canonical_str.strip().lower()

	col_by_lower: Dict[str, str] = {}
	col_by_norm: Dict[str, str] = {}
	for c in col_list:
		cl = c.lower()
		if cl not in col_by_lower:
			col_by_lower[cl] = c
		cn = _normalize_col_name(c)
		if cn not in col_by_norm:
			col_by_norm[cn] = c

	def _match_single(candidate: str) -> Optional[str]:
		if candidate in col_list:
			return candidate
		cl = candidate.lower()
		if cl in col_by_lower:
			return col_by_lower[cl]
		if normalized_match:
			cn = _normalize_col_name(candidate)
			if cn in col_by_norm:
				return col_by_norm[cn]
		return None

	base_aliases = DEFAULT_SYSTEM_COLUMN_ALIASES.get(canonical_lower, [])
	candidates = _dedupe_candidates(
		[canonical_str, *(extra_aliases or []), *base_aliases]
	)

	req_clean = requested_col.strip() if isinstance(requested_col, str) else None
	if req_clean and req_clean.lower() != "auto":
		matched = _match_single(req_clean)
		if matched is not None:
			return matched
		if strict_requested:
			req_norm = _normalize_col_name(req_clean)
			known_norms = {_normalize_col_name(a) for a in candidates}
			if req_norm not in known_norms:
				return None

	# Priority 1: exact match across all candidates
	for cand in candidates:
		if cand in col_list:
			return cand

	# Priority 2: case-insensitive match
	for cand in candidates:
		cl = cand.lower()
		if cl in col_by_lower:
			return col_by_lower[cl]

	# Priority 3: normalized match (ignore _, -, space)
	if normalized_match:
		for cand in candidates:
			cn = _normalize_col_name(cand)
			if cn in col_by_norm:
				return col_by_norm[cn]

	return None


def build_non_ml_columns(
	metadata_list: Optional[Iterable[SystemColumnMetadata]] = None,
	extra_non_ml_columns: Optional[Iterable[str]] = None,
) -> Set[str]:
	"""Builds the lowercase set of column names excluded from ML mathematical feature encoding."""
	non_ml: Set[str] = set()
	for core_key in ("event_id", "timestamp", "user_id", "label"):
		non_ml.add(core_key)
		for alias in DEFAULT_SYSTEM_COLUMN_ALIASES.get(core_key, []):
			non_ml.add(alias.lower())

	if metadata_list is not None:
		for meta in metadata_list:
			role_val = meta.ml_role.value if hasattr(meta.ml_role, "value") else str(meta.ml_role)
			if role_val.upper() != ColumnMlRole.FEATURE.value:
				non_ml.add(meta.column_key.strip().lower())
				for alias in meta.aliases or []:
					cleaned = str(alias).strip().lower()
					if cleaned:
						non_ml.add(cleaned)

	if extra_non_ml_columns is not None:
		for col in extra_non_ml_columns:
			cleaned = str(col).strip().lower()
			if cleaned:
				non_ml.add(cleaned)

	return non_ml


__all__ = [
	"CORE_COLUMN_KEYS",
	"DEFAULT_SYSTEM_COLUMN_ALIASES",
	"DEFAULT_SYSTEM_COLUMN_SPECS",
	"build_default_system_columns",
	"resolve_canonical_column",
	"build_non_ml_columns",
]
