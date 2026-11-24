"""Seed templates for NETWORK built-in PYTHON_CODE features."""

DEVICE_DISTINCT_USERS_CODE = '''import pandas as pd

def compute(df: pd.DataFrame, params: dict) -> pd.Series:
	entity_col = params.get("entity_col", "device_id")
	user_col = params.get("user_col", "user_id")
	if entity_col not in df.columns or user_col not in df.columns:
		return pd.Series(0.0, index=df.index, dtype=float)
	counts = df.groupby(entity_col, dropna=False)[user_col].transform("nunique")
	mask = df[entity_col].isna() | (df[entity_col].astype(str).str.strip() == "")
	counts = counts.where(~mask, 0)
	return counts.astype(float)
'''

IP_DISTINCT_USERS_CODE = '''import pandas as pd

def compute(df: pd.DataFrame, params: dict) -> pd.Series:
	entity_col = params.get("entity_col", "ip_address")
	user_col = params.get("user_col", "user_id")
	if entity_col not in df.columns or user_col not in df.columns:
		return pd.Series(0.0, index=df.index, dtype=float)
	counts = df.groupby(entity_col, dropna=False)[user_col].transform("nunique")
	mask = df[entity_col].isna() | (df[entity_col].astype(str).str.strip() == "")
	counts = counts.where(~mask, 0)
	return counts.astype(float)
'''

CARD_DISTINCT_USERS_CODE = '''import pandas as pd

def compute(df: pd.DataFrame, params: dict) -> pd.Series:
	entity_col = params.get("entity_col", "card_id")
	user_col = params.get("user_col", "user_id")
	if entity_col not in df.columns or user_col not in df.columns:
		return pd.Series(0.0, index=df.index, dtype=float)
	counts = df.groupby(entity_col, dropna=False)[user_col].transform("nunique")
	mask = df[entity_col].isna() | (df[entity_col].astype(str).str.strip() == "")
	counts = counts.where(~mask, 0)
	return counts.astype(float)
'''

MERCHANT_DISTINCT_USERS_CODE = '''import pandas as pd

def compute(df: pd.DataFrame, params: dict) -> pd.Series:
	entity_col = params.get("entity_col", "merchant")
	user_col = params.get("user_col", "user_id")
	if entity_col not in df.columns or user_col not in df.columns:
		return pd.Series(0.0, index=df.index, dtype=float)
	counts = df.groupby(entity_col, dropna=False)[user_col].transform("nunique")
	mask = df[entity_col].isna() | (df[entity_col].astype(str).str.strip() == "")
	counts = counts.where(~mask, 0)
	return counts.astype(float)
'''

COMMUNITY_SIZE_CODE = '''import pandas as pd

def compute(df: pd.DataFrame, params: dict) -> pd.Series:
	user_col = params.get("user_col", "user_id")
	link_cols = [c for c in (params.get("link_cols") or ["device_id", "ip_address", "card_id"]) if c in df.columns]
	if user_col not in df.columns or not link_cols or len(df) == 0:
		return pd.Series(1.0, index=df.index, dtype=float)

	parent = {}
	def _find(x):
		while parent.get(x, x) != x:
			parent[x] = parent.get(parent[x], parent[x])
			x = parent[x]
		return x
	def _union(a, b):
		ra, rb = _find(a), _find(b)
		if ra != rb:
			parent[rb] = ra

	user_nodes = [f"u:{str(u)}" for u in df[user_col]]
	for idx, u_node in enumerate(user_nodes):
		parent.setdefault(u_node, u_node)
		for col in link_cols:
			raw_val = df[col].iloc[idx]
			if pd.isna(raw_val):
				continue
			val_s = str(raw_val).strip()
			if not val_s:
				continue
			e_node = f"{col}:{val_s}"
			parent.setdefault(e_node, e_node)
			_union(u_node, e_node)

	comp_users = {}
	for u_node in set(user_nodes):
		root = _find(u_node)
		comp_users[root] = comp_users.get(root, 0) + 1

	sizes = [float(comp_users.get(_find(u_node), 1)) for u_node in user_nodes]
	return pd.Series(sizes, index=df.index, dtype=float)
'''

COMMUNITY_FRAUD_RATIO_CODE = '''import pandas as pd

def fit(train_df: pd.DataFrame, params: dict) -> dict:
	user_col = params.get("user_col", "user_id")
	label_col = params.get("label_col", "label")
	link_cols = [c for c in (params.get("link_cols") or ["device_id", "ip_address", "card_id"]) if c in train_df.columns]
	smoothing_m = float(params.get("smoothing_m", 5.0))
	if user_col not in train_df.columns or label_col not in train_df.columns or len(train_df) == 0:
		return {"prior": 0.0, "user_rates": {}, "entity_rates": {}}

	labels = pd.to_numeric(train_df[label_col], errors="coerce").fillna(0.0)
	prior = float(labels.mean()) if len(labels) > 0 else 0.0

	parent = {}
	def _find(x):
		while parent.get(x, x) != x:
			parent[x] = parent.get(parent[x], parent[x])
			x = parent[x]
		return x
	def _union(a, b):
		ra, rb = _find(a), _find(b)
		if ra != rb:
			parent[rb] = ra

	user_nodes = [f"u:{str(u)}" for u in train_df[user_col]]
	entities_seen = []
	for idx, u_node in enumerate(user_nodes):
		parent.setdefault(u_node, u_node)
		for col in link_cols:
			raw_val = train_df[col].iloc[idx]
			if pd.isna(raw_val):
				continue
			val_s = str(raw_val).strip()
			if not val_s:
				continue
			e_node = f"{col}:{val_s}"
			parent.setdefault(e_node, e_node)
			_union(u_node, e_node)
			entities_seen.append(e_node)

	comp_stats = {}
	for u_node, lbl in zip(user_nodes, labels):
		root = _find(u_node)
		cnt, fsum = comp_stats.get(root, (0, 0.0))
		comp_stats[root] = (cnt + 1, fsum + float(lbl))

	def _smoothed(root):
		cnt, fsum = comp_stats.get(root, (0, 0.0))
		return round((fsum + smoothing_m * prior) / (cnt + smoothing_m), 6) if (cnt + smoothing_m) > 0 else prior

	user_rates = {u_node[2:]: _smoothed(_find(u_node)) for u_node in set(user_nodes)}
	entity_rates = {e_node: _smoothed(_find(e_node)) for e_node in set(entities_seen)}
	return {"prior": round(prior, 6), "user_rates": user_rates, "entity_rates": entity_rates}

def compute(df: pd.DataFrame, params: dict, state: dict) -> pd.Series:
	user_col = params.get("user_col", "user_id")
	link_cols = [c for c in (params.get("link_cols") or ["device_id", "ip_address", "card_id"]) if c in df.columns]
	st = state or {}
	prior = float(st.get("prior", 0.0))
	user_rates = st.get("user_rates") or {}
	entity_rates = st.get("entity_rates") or {}

	out = []
	for idx in range(len(df)):
		u_val = str(df[user_col].iloc[idx]) if user_col in df.columns else ""
		if u_val in user_rates:
			out.append(float(user_rates[u_val]))
			continue
		matched = None
		for col in link_cols:
			raw_val = df[col].iloc[idx]
			if pd.isna(raw_val):
				continue
			key = f"{col}:{str(raw_val).strip()}"
			if key in entity_rates:
				matched = float(entity_rates[key])
				break
		out.append(matched if matched is not None else prior)
	return pd.Series(out, index=df.index, dtype=float)
'''
