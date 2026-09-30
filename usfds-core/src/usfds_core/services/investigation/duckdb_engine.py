"""DuckDB Analytical Engine for zero-copy querying of FDS artifacts."""

from pathlib import Path
from typing import Any, Dict, List, Optional
import duckdb

from usfds_core.domain.schemas.investigation_schemas import (
    CaseSummary,
    RelatedCase,
    UserBaselineProfile,
)


class DuckDBInvestigationEngine:
    """Analytical engine querying Parquet artifacts directly using DuckDB."""

    def __init__(
        self,
        test_enriched_path: str,
        eval_predictions_path: str,
        train_enriched_path: Optional[str] = None,
    ):
        self.test_enriched_path = Path(test_enriched_path).resolve().as_posix()
        self.eval_predictions_path = Path(eval_predictions_path).resolve().as_posix()
        self.train_enriched_path = (
            Path(train_enriched_path).resolve().as_posix()
            if train_enriched_path and Path(train_enriched_path).exists()
            else None
        )
        self.conn = duckdb.connect(":memory:")
        self._init_views()

    def _init_views(self) -> None:
        """Initializes virtual views joining predictions with enriched transactional attributes."""
        # Row-aligned 1-to-1 join via monotonic row numbers
        self.conn.execute(f"""
            CREATE OR REPLACE VIEW v_eval_cases AS
            SELECT 
                e.event_id,
                e.user_id,
                e.amount,
                e.avg_amount_user,
                e.total_transactions_user,
                e.account_age_days,
                e.country,
                e.bin_country,
                e.channel,
                e.merchant_category,
                e.promo_used,
                e.avs_match,
                e.cvv_result,
                e.three_ds_flag,
                e.shipping_distance_km,
                e.timestamp,
                p.y_prob,
                p.y_true,
                e.rn AS row_idx
            FROM (
                SELECT *, row_number() OVER () - 1 AS rn 
                FROM read_parquet('{self.test_enriched_path}')
            ) e
            JOIN (
                SELECT *, row_number() OVER () - 1 AS rn 
                FROM read_parquet('{self.eval_predictions_path}')
            ) p ON e.rn = p.rn
        """)

        # User historical activity view (unions train and test if available)
        if self.train_enriched_path:
            self.conn.execute(f"""
                CREATE OR REPLACE VIEW v_all_transactions AS
                SELECT event_id, user_id, amount, account_age_days, country, bin_country, channel, merchant_category, timestamp, label
                FROM read_parquet('{self.test_enriched_path}')
                UNION ALL
                SELECT event_id, user_id, amount, account_age_days, country, bin_country, channel, merchant_category, timestamp, label
                FROM read_parquet('{self.train_enriched_path}')
            """)
        else:
            self.conn.execute(f"""
                CREATE OR REPLACE VIEW v_all_transactions AS
                SELECT event_id, user_id, amount, account_age_days, country, bin_country, channel, merchant_category, timestamp, label
                FROM read_parquet('{self.test_enriched_path}')
            """)

    def get_case_summary(self, event_id: int) -> Optional[CaseSummary]:
        """Retrieves single transaction case summary with fraud score and risk level."""
        df = self.conn.execute(
            """
            SELECT * FROM v_eval_cases WHERE event_id = ?
            """,
            [event_id],
        ).df()

        if df.empty:
            return None

        row = df.iloc[0]
        y_prob = float(row["y_prob"])

        # Map to Risk Level
        if y_prob >= 0.80:
            risk_level = "CRITICAL"
        elif y_prob >= 0.50:
            risk_level = "HIGH"
        elif y_prob >= 0.20:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return CaseSummary(
            event_id=int(row["event_id"]),
            user_id=int(row["user_id"]),
            amount=float(row["amount"]),
            avg_amount_user=float(row["avg_amount_user"]) if row["avg_amount_user"] is not None else None,
            total_transactions_user=int(row["total_transactions_user"]) if row["total_transactions_user"] is not None else None,
            account_age_days=int(row["account_age_days"]) if row["account_age_days"] is not None else None,
            country=str(row["country"]) if row["country"] is not None else None,
            bin_country=str(row["bin_country"]) if row["bin_country"] is not None else None,
            channel=str(row["channel"]) if row["channel"] is not None else None,
            merchant_category=str(row["merchant_category"]) if row["merchant_category"] is not None else None,
            promo_used=int(row["promo_used"]) if row["promo_used"] is not None else None,
            avs_match=int(row["avs_match"]) if row["avs_match"] is not None else None,
            cvv_result=int(row["cvv_result"]) if row["cvv_result"] is not None else None,
            three_ds_flag=int(row["three_ds_flag"]) if row["three_ds_flag"] is not None else None,
            shipping_distance_km=float(row["shipping_distance_km"]) if row["shipping_distance_km"] is not None else None,
            timestamp=str(row["timestamp"]) if row["timestamp"] is not None else None,
            y_prob=round(y_prob, 4),
            y_true=int(row["y_true"]) if row["y_true"] is not None else None,
            risk_level=risk_level,
        )

    def get_row_index_by_event_id(self, event_id: int) -> Optional[int]:
        """Returns the physical row index in the evaluation dataset."""
        res = self.conn.execute(
            "SELECT row_idx FROM v_eval_cases WHERE event_id = ?", [event_id]
        ).fetchone()
        return res[0] if res else None

    def get_user_baseline(self, user_id: int, current_event_id: Optional[int] = None) -> UserBaselineProfile:
        """Aggregates user spending profile and detects deviations."""
        # Summary statistics for this user
        stats_df = self.conn.execute(
            """
            SELECT 
                COUNT(*) as tx_count,
                COALESCE(AVG(amount), 0.0) as avg_amount,
                COALESCE(MAX(amount), 0.0) as max_amount,
                COALESCE(MAX(account_age_days), 0) as account_age
            FROM v_all_transactions
            WHERE user_id = ?
            """,
            [user_id],
        ).df()

        # Known merchant categories
        cat_df = self.conn.execute(
            """
            SELECT merchant_category, COUNT(*) as cnt
            FROM v_all_transactions
            WHERE user_id = ? AND merchant_category IS NOT NULL
            GROUP BY merchant_category
            ORDER BY cnt DESC
            LIMIT 5
            """,
            [user_id],
        ).df()

        # Known countries
        country_df = self.conn.execute(
            """
            SELECT country, COUNT(*) as cnt
            FROM v_all_transactions
            WHERE user_id = ? AND country IS NOT NULL
            GROUP BY country
            ORDER BY cnt DESC
            LIMIT 5
            """,
            [user_id],
        ).df()

        tx_count = int(stats_df.iloc[0]["tx_count"])
        avg_amount = float(stats_df.iloc[0]["avg_amount"])
        max_amount = float(stats_df.iloc[0]["max_amount"])
        account_age = int(stats_df.iloc[0]["account_age"])

        frequent_categories = cat_df["merchant_category"].tolist() if not cat_df.empty else []
        known_countries = country_df["country"].tolist() if not country_df.empty else []

        # Current transaction check
        amount_deviation_ratio = 1.0
        is_new_country = False
        is_new_merchant_category = False

        if current_event_id is not None:
            curr_df = self.conn.execute(
                "SELECT amount, country, merchant_category FROM v_eval_cases WHERE event_id = ?",
                [current_event_id],
            ).df()
            if not curr_df.empty:
                curr_row = curr_df.iloc[0]
                curr_amount = float(curr_row["amount"])
                if avg_amount > 0:
                    amount_deviation_ratio = round(curr_amount / avg_amount, 2)
                curr_country = str(curr_row["country"])
                curr_cat = str(curr_row["merchant_category"])

                if known_countries and curr_country not in known_countries:
                    is_new_country = True
                if frequent_categories and curr_cat not in frequent_categories:
                    is_new_merchant_category = True

        return UserBaselineProfile(
            user_id=user_id,
            account_age_days=account_age,
            total_transactions_history=tx_count,
            avg_amount_history=round(avg_amount, 2),
            max_amount_history=round(max_amount, 2),
            frequent_merchant_categories=frequent_categories,
            known_countries=known_countries,
            amount_deviation_ratio=amount_deviation_ratio,
            is_new_country=is_new_country,
            is_new_merchant_category=is_new_merchant_category,
        )

    def search_related_cases(self, event_id: int, limit: int = 5) -> List[RelatedCase]:
        """Finds related transactions: same cardholder, or same cross-border / shipping patterns."""
        curr_case = self.get_case_summary(event_id)
        if not curr_case:
            return []

        related: List[RelatedCase] = []

        # 1. Other transactions from the same user_id
        user_df = self.conn.execute(
            """
            SELECT event_id, user_id, amount, shipping_distance_km, country, bin_country, timestamp, y_prob, y_true
            FROM v_eval_cases
            WHERE user_id = ? AND event_id != ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            [curr_case.user_id, event_id, limit],
        ).df()

        for _, row in user_df.iterrows():
            related.append(
                RelatedCase(
                    event_id=int(row["event_id"]),
                    user_id=int(row["user_id"]),
                    amount=float(row["amount"]),
                    shipping_distance_km=float(row["shipping_distance_km"]) if row["shipping_distance_km"] is not None else None,
                    country=str(row["country"]) if row["country"] is not None else None,
                    bin_country=str(row["bin_country"]) if row["bin_country"] is not None else None,
                    timestamp=str(row["timestamp"]) if row["timestamp"] is not None else None,
                    y_prob=round(float(row["y_prob"]), 4),
                    y_true=int(row["y_true"]) if row["y_true"] is not None else None,
                    similarity_reason=f"Cùng chủ tài khoản (user_id={curr_case.user_id})",
                )
            )

        # 2. Correlated high-risk cross-border orders in same country/bin_country
        if len(related) < limit and curr_case.country and curr_case.bin_country:
            cross_df = self.conn.execute(
                """
                SELECT event_id, user_id, amount, shipping_distance_km, country, bin_country, timestamp, y_prob, y_true
                FROM v_eval_cases
                WHERE country = ? AND bin_country = ? AND event_id != ? AND user_id != ? AND y_prob > 0.70
                ORDER BY y_prob DESC
                LIMIT ?
                """,
                [curr_case.country, curr_case.bin_country, event_id, curr_case.user_id, limit - len(related)],
            ).df()

            for _, row in cross_df.iterrows():
                related.append(
                    RelatedCase(
                        event_id=int(row["event_id"]),
                        user_id=int(row["user_id"]),
                        amount=float(row["amount"]),
                        shipping_distance_km=float(row["shipping_distance_km"]) if row["shipping_distance_km"] is not None else None,
                        country=str(row["country"]) if row["country"] is not None else None,
                        bin_country=str(row["bin_country"]) if row["bin_country"] is not None else None,
                        timestamp=str(row["timestamp"]) if row["timestamp"] is not None else None,
                        y_prob=round(float(row["y_prob"]), 4),
                        y_true=int(row["y_true"]) if row["y_true"] is not None else None,
                        similarity_reason=f"Cùng mẫu tuyến giao dịch rủi ro cao ({curr_case.country} -> BIN {curr_case.bin_country})",
                    )
                )

        return related
