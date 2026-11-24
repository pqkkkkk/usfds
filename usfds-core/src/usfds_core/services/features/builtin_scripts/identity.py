"""Seed templates for IDENTITY built-in PYTHON_CODE features."""

EMAIL_DOMAIN_CODE = '''import pandas as pd

def compute(df: pd.DataFrame, params: dict) -> pd.Series:
	col = params.get("col", "email")
	if col not in df.columns:
		return pd.Series("", index=df.index, dtype=object)
	vals = df[col].fillna("").astype(str).str.strip().str.lower()
	return vals.apply(lambda v: v.split("@", 1)[1] if "@" in v else "")
'''

EMAIL_DIGIT_RATIO_CODE = '''import pandas as pd

def compute(df: pd.DataFrame, params: dict) -> pd.Series:
	col = params.get("col", "email")
	if col not in df.columns:
		return pd.Series(0.0, index=df.index, dtype=float)
	def _ratio(val):
		s = str(val or "").strip()
		local = s.split("@", 1)[0] if "@" in s else s
		if not local:
			return 0.0
		digits = sum(1 for ch in local if ch.isdigit())
		return float(digits) / float(len(local))
	return df[col].apply(_ratio).astype(float)
'''

IS_FREE_EMAIL_CODE = '''import pandas as pd

_FREE_DOMAINS = {
	"gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "hotmail.com",
	"outlook.com", "live.com", "icloud.com", "aol.com", "protonmail.com", "proton.me",
}

def compute(df: pd.DataFrame, params: dict) -> pd.Series:
	col = params.get("col", "email")
	if col not in df.columns:
		return pd.Series(False, index=df.index, dtype=bool)
	extra = {str(d).strip().lower() for d in (params.get("extra_domains") or [])}
	domains = _FREE_DOMAINS | extra
	def _is_free(val):
		s = str(val or "").strip().lower()
		dom = s.split("@", 1)[1] if "@" in s else s
		return dom in domains
	return df[col].apply(_is_free).astype(bool)
'''

IP_PREFIX_24_CODE = '''import ipaddress
import pandas as pd

def compute(df: pd.DataFrame, params: dict) -> pd.Series:
	col = params.get("col", "ip_address")
	if col not in df.columns:
		return pd.Series("", index=df.index, dtype=object)
	def _prefix(val):
		s = str(val or "").strip()
		if not s:
			return ""
		try:
			addr = ipaddress.ip_address(s)
			if addr.version == 4:
				parts = s.split(".")
				return ".".join(parts[:3]) + ".0/24"
			return str(ipaddress.ip_network(f"{s}/64", strict=False).network_address) + "/64"
		except ValueError:
			return ""
	return df[col].apply(_prefix).astype(object)
'''

IP_IS_PRIVATE_CODE = '''import ipaddress
import pandas as pd

def compute(df: pd.DataFrame, params: dict) -> pd.Series:
	col = params.get("col", "ip_address")
	if col not in df.columns:
		return pd.Series(False, index=df.index, dtype=bool)
	def _is_priv(val):
		s = str(val or "").strip()
		if not s:
			return False
		try:
			addr = ipaddress.ip_address(s)
			return bool(addr.is_private or addr.is_loopback or addr.is_reserved)
		except ValueError:
			return False
	return df[col].apply(_is_priv).astype(bool)
'''

UA_IS_MOBILE_CODE = '''import re
import pandas as pd

_MOBILE_RE = re.compile(r"(mobile|android|iphone|ipad|ipod|blackberry|opera mini|iemobile)", re.IGNORECASE)

def compute(df: pd.DataFrame, params: dict) -> pd.Series:
	col = params.get("col", "user_agent")
	if col not in df.columns:
		return pd.Series(False, index=df.index, dtype=bool)
	return df[col].fillna("").astype(str).apply(lambda s: bool(_MOBILE_RE.search(s))).astype(bool)
'''

UA_IS_BOT_CODE = '''import re
import pandas as pd

_BOT_RE = re.compile(r"(bot|crawler|spider|scrapy|curl|wget|python-requests|httpclient|headless)", re.IGNORECASE)

def compute(df: pd.DataFrame, params: dict) -> pd.Series:
	col = params.get("col", "user_agent")
	if col not in df.columns:
		return pd.Series(False, index=df.index, dtype=bool)
	return df[col].fillna("").astype(str).apply(lambda s: bool(_BOT_RE.search(s))).astype(bool)
'''

PHONE_AREA_CODE = '''import re
import pandas as pd

def compute(df: pd.DataFrame, params: dict) -> pd.Series:
	col = params.get("col", "phone_number")
	if col not in df.columns:
		return pd.Series("", index=df.index, dtype=object)
	def _area(val):
		digits = re.sub(r"\\D+", "", str(val or ""))
		if len(digits) >= 10 and digits.startswith("1"):
			digits = digits[1:]
		return digits[:3] if len(digits) >= 3 else digits
	return df[col].apply(_area).astype(object)
'''
