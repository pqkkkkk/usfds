from typing import Any, Union
import numpy as np
import pandas as pd


class NumericTypeCoercer:
    """Safely cleans and coerces messy/mixed-type numeric columns into standard float values.

    Handles currency symbols ($ ₫ € ¥ £), thousands separators (commas),
    spaces, parentheses for negative amounts, and common string placeholders (N/A, null, unknown).
    """

    @staticmethod
    def coerce_numeric(series: pd.Series) -> pd.Series:
        if pd.api.types.is_numeric_dtype(series):
            return series.astype(float)

        def _clean_val(val: Any) -> Union[float, Any]:
            if pd.isna(val) or val is None:
                return np.nan
            if isinstance(val, (int, float, np.number)):
                return float(val)

            val_str = str(val).strip()
            if not val_str or val_str.lower() in {"na", "n/a", "null", "none", "unknown", "-", ""}:
                return np.nan

            # Handle accounting parentheses negative format, e.g. (100.5) -> -100.5
            is_negative = False
            if val_str.startswith("(") and val_str.endswith(")"):
                is_negative = True
                val_str = val_str[1:-1].strip()

            # Remove currency symbols and non-numeric artifacts except dot, minus
            cleaned = val_str.replace(",", "").replace("$", "").replace("₫", "").replace("€", "").replace("¥", "").replace("£", "")
            cleaned = "".join(ch for ch in cleaned if ch.isdigit() or ch in {".", "-"})

            try:
                num = float(cleaned)
                return -num if is_negative else num
            except (ValueError, TypeError):
                return np.nan

        return series.map(_clean_val).astype(float)


__all__ = ["NumericTypeCoercer"]
