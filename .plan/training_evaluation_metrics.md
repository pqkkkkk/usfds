# Plan: Upgrade Model Training Evaluation Metrics (`TASK-105`)

> **Source Specification:** [Notion — Độ đo (metrics) đánh giá (`TASK-105`)](https://app.notion.com/p/o-metrics-nh-gi-670b99c6a95082799942018c3616dd9b)  
> **Related Spec:** `docs/features/detection/training/suc-spec.md` (`SUC-09`, `SUC-27`)  
> **Date:** 10/11/2026 (`[26-11-10]`)

---

## 1. Scope: Strict Alignment with Notion `TASK-105`

### 1.1. Supported Metrics (Strictly from Notion Doc)
1. **Section 0 — Confusion Matrix (`confusion_matrix`):** `TP`, `FP`, `FN`, `TN`
2. **Section 1 — Threshold-dependent Metrics (Transaction-level):**
   - **1.1. Accuracy (`accuracy`):** $(TP + TN) / (TP + TN + FP + FN)$
   - **1.2. Precision (`precision`):** $TP / (TP + FP)$
   - **1.3. Recall / Sensitivity / TPR (`recall`):** $TP / (TP + FN)$
   - **1.4. F1 Score & F2 Score (`f1_score`, `f2_score`):** $2TP / (2TP + FP + FN)$ and $F_{\beta=2}$
   - **1.5. MCC (`mcc`):** $(TP \cdot TN - FP \cdot FN) / \sqrt{(TP+FP)(TP+FN)(TN+FP)(TN+FN)} \in [-1, +1]$
3. **Section 2 — Threshold-free / Curve-based Metrics (Transaction-level):**
   - **2.1. AUC-ROC (`roc_auc`, `roc_curve`):** Area under ROC curve (`FPR` vs `TPR`)
   - **2.2. AUC-PR / Average Precision (`pr_auc`, `pr_curve`):** Area under Precision-Recall curve (`Recall` vs `Precision`)
4. **Section 3 — Business-aligned Operational Metrics:**
   - **3.1. Precision@$k$ (`precision_at_k`, `precision_at_100`):** $|A_d^{\text{true}}| / k$ for $k \in \{50, 100, 200, 500\}$ (supports both `daily_avg` per day $d$ when timestamps exist and `overall` test set)
   - **3.2. Precision@0.2 Recall (`precision_at_0_2_recall`):** $\frac{1}{0.2} \int_0^{0.2} \text{Precision}(r) \, dr$
   - **3.4. AUC-PR Card (`auc_pr_card`, `pr_curve_card`):** AUC-PR on card-level max probability $\hat{p}_{\text{card}}(c) = \max_{x \in T(c)} \hat{p}(x)$ and label $Y_{\text{card}}(c) = \max_{x \in T(c)} Y(x)$
   - **3.5. Card Precision@$k$ / `CP@k` (`card_precision_at_k`, `cp_at_100`):** $|C_d^{\text{true}}| / k$ on top-$k$ unique cards ($k \in \{50, 100, 200, 500\}$, both `daily_avg` and `overall`)

### 1.2. Unmentioned Metrics & Presets to Deprecate/Remove
Per coding guidelines (*Preserve Code: Comment out unused code and tag as `DEPRECATED`*):
- **Remove from `MetricEvaluator` & `_usfds_runner.py`:**
  - `youden_j` (Youden's J statistic), `high_recall_90`, `high_recall_95` in `recommended_thresholds` (keep only `best_f1`, `best_f2`, `best_mcc`).
  - `score_distribution` / `compute_score_distribution` (not part of the Notion metrics specification).
  - `log_loss` / `loss` calculation in `_usfds_runner.py` (not in Notion doc).
  - Legacy `ks_statistic` and `inference_latency_ms` in `usfds-web/src/types/model.ts`.

---

## 2. Step-by-Step Implementation Plan

1. **[docs] Update `docs/features/detection/training/suc-spec.md` (`[26-11-10]`):**
   - Update `SUC-09` and `SUC-27` to list only the 11 metrics in `TASK-105` and replace `Score Distribution Histogram`, `Loss`, `Youden's J`, `Target Recall >= 90%/95%` with `MCC`, `Precision@k`, `Precision@0.2 Recall`, `AUC-PR Card`, `Card Precision@k (CP@k)`, and `PR Curve (Card-level)` chart.
2. **[core] Upgrade `MetricEvaluator` (`usfds-core/src/usfds_core/services/training/evaluators/metric_evaluator.py`):**
   - Implement `mcc` (default + 100-step `threshold_tuning_grid` + `recommended_thresholds` with `best_f1`, `best_f2`, `best_mcc`).
   - Deprecate `youden_j`, `high_recall_90`, `high_recall_95`, and `compute_score_distribution`.
   - Implement `compute_precision_at_0_2_recall(y_true, y_prob)`.
   - Implement `compute_precision_at_k(y_true, y_prob, timestamps=None, k_values=(50, 100, 200, 500))`.
   - Implement `compute_card_level_metrics(y_true, y_prob, card_ids, timestamps=None, k_values=(50, 100, 200, 500))` producing `auc_pr_card`, `pr_curve_card`, `card_precision_at_k`, `cp_at_100`, and `card_metrics_meta`.
3. **[core] Wire `card_ids` and `timestamps` in `BuiltinModelTrainer`, `ScriptPluginTrainer`, and `_usfds_runner.py`:**
   - Extract canonical card column (`user_id`, `card_id`, `customer_id`, `client_id`, `account_id`) and timestamp column (`timestamp`, `time`, `datetime`, `tx_time`, `date_time`) from the evaluation dataset before dropping `NON_ML_COLUMNS`.
   - Pass `card_ids` and `timestamps` into `MetricEvaluator.evaluate(...)` for both `BUILTIN` and `SCRIPT` models.
   - Deprecate `log_loss` in `_usfds_runner.py`.
4. **[core/tests] Update & Add Unit Tests (`usfds-core/tests/training/test_metric_evaluator.py`):**
   - Verify all 11 Notion metrics (`Confusion Matrix`, `Accuracy`, `Precision`, `Recall`, `F1`, `F2`, `MCC`, `AUC-ROC`, `AUC-PR`, `Precision@k`, `Precision@0.2 Recall`, `AUC-PR Card`, `CP@k`) and confirm removed metrics (`youden_j`, `high_recall_90`, `high_recall_95`, `score_distribution`) are no longer emitted.
5. **[fe] Update Types & UI (`usfds-web`):**
   - Update `usfds-web/src/types/metrics.ts` and `usfds-web/src/types/model.ts`.
   - Update `TrainingRunDetailView.tsx` (`SUC-09`) to render the 3 metric groups from Notion (`Threshold-dependent`, `Threshold-free`, `Business-aligned Operational Metrics` with $k \in \{50, 100, 200, 500\}$ & `Daily Avg`/`Overall` toggle) and 3 curves (`ROC Curve`, `Transaction PR Curve`, `Card-level PR Curve`).
   - Update `ModelHubView.tsx` (`SUC-27`) to include `MCC` and `CP@100` / `AUC-PR Card` in the runs table.
6. **[verify] Run `pytest` and `npm run build`:**
   - Verify all unit/API tests in `usfds-core` and `usfds-server` pass and `npm run build` in `usfds-web` succeeds with zero errors.
