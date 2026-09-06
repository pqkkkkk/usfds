from typing import Optional
import pandas as pd

from usfds_core.domain.schemas.preprocessing_config import SupportedTimeFormat


class TimestampNormalizer:
    """Standardizes varied timestamp inputs (ISO strings, epoch seconds/ms, custom strftime) into UTC datetime or standard float."""

    @staticmethod
    def normalize(series: pd.Series, time_format: Optional[str] = SupportedTimeFormat.AUTO.value) -> pd.Series:
        if series.empty:
            return series

        # Handle numeric timestamps (epoch seconds, milliseconds, or relative seconds)
        if pd.api.types.is_numeric_dtype(series):
            valid_nums = series.dropna()
            if valid_nums.empty:
                return pd.to_datetime(series, utc=True, errors="coerce")

            max_val = float(valid_nums.max())
            if max_val > 1e11:  # Epoch milliseconds (13 digits, e.g. 1696170600000)
                return pd.to_datetime(series, unit="ms", utc=True, errors="coerce")
            elif max_val > 1e8:  # Epoch seconds (10 digits, e.g. 1696170600)
                return pd.to_datetime(series, unit="s", utc=True, errors="coerce")
            else:
                # Relative elapsed time from origin (e.g. 0 to 172792 as in Kaggle credit card dataset)
                return series.astype(float)

        # Handle string timestamps
        fmt = (time_format or "auto").lower()
        if fmt in {"epoch_s", "epoch_seconds"}:
            numeric_vals = pd.to_numeric(series, errors="coerce")
            return pd.to_datetime(numeric_vals, unit="s", utc=True, errors="coerce")
        elif fmt in {"epoch_ms", "epoch_millis"}:
            numeric_vals = pd.to_numeric(series, errors="coerce")
            return pd.to_datetime(numeric_vals, unit="ms", utc=True, errors="coerce")
        elif fmt == "iso":
            return pd.to_datetime(series, format="ISO8601", utc=True, errors="coerce")
        elif time_format and time_format not in {"auto", SupportedTimeFormat.AUTO.value}:
            return pd.to_datetime(series, format=time_format, utc=True, errors="coerce")
        else:
            # Auto detection
            return pd.to_datetime(series, utc=True, errors="coerce")


__all__ = ["TimestampNormalizer"]
