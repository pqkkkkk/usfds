# 04 — Data Model (ERD, relations level)
<!-- [26-11-28] Created: relations-level ERD of the 27 ORM tables, grouped by owning module. -->

Relations-level view of the OLTP schema: tables, primary / foreign keys, cardinality, and only the columns that carry a cross-module contract (`project_id`, `user_id`, `status`, versions, artifact references). Full columns and types live in the ORM (`usfds-infra/src/usfds_infra/database/tables/*.py`, `case_models.py`); schema changes go only through Alembic (`INV-006`).

Conventions:
- Solid line = DB foreign key. Dotted line = **soft reference** (ID column without FK; integrity is enforced in code).
- `users` / `projects` appear as stubs in several diagrams; they are owned by module 1.
- `project_id` nullable (`null`) = system-wide built-in row.
- `user_id` FKs to `users` use `ON DELETE RESTRICT` unless the edge is labelled otherwise (`INV-011`); `project_id` FKs use `ON DELETE CASCADE`.

## 1. Auth, RBAC & projects — [module 1](modules/auth-and-access.md)

```mermaid
erDiagram
    users ||--o{ user_sessions : "has (cascade)"
    users ||--o{ system_user_roles : "granted (cascade)"
    roles ||--o{ system_user_roles : "assigned"
    roles ||--o{ role_permissions : "has"
    permissions ||--o{ role_permissions : "in"
    users ||--o{ projects : "owns (restrict)"
    projects ||--o{ project_members : "has (cascade)"
    users ||--o{ project_members : "member (cascade)"
    roles ||--o{ project_members : "role"

    users {
        string user_id PK
        string status "ACTIVE | DISABLED"
    }
    roles {
        string role_id PK
        string scope "SYSTEM | PROJECT, UQ(scope, name)"
    }
    permissions {
        string permission_id PK
        string scope
    }
    projects {
        string project_id PK
        string user_id FK
        string status "ACTIVE | ARCHIVED"
        json raw_schema "locked by ingestion"
    }
    project_members {
        string project_id PK
        string user_id PK
        string role_id PK
    }
```

## 2. Data, system metadata & features — [module 2](modules/data-and-features.md)

```mermaid
erDiagram
    projects ||--o{ datasets : "cascade"
    users ||--o{ datasets : "restrict"
    datasets ||--o{ dataset_artifacts : "cascade"
    dataset_artifacts |o--o{ dataset_artifacts : "parent_artifact_id (lineage C2)"
    projects |o--o{ features : "null = built-in"
    features ||--o{ feature_dependencies : "feature (cascade)"
    features ||--o{ feature_dependencies : "depends_on (restrict)"
    projects |o--o{ feature_sets : "null = built-in"
    feature_sets ||--o{ feature_set_items : "cascade"
    features ||--o{ feature_set_items : "restrict"
    dataset_artifacts ||--o{ dataset_artifact_features : "cascade"
    features |o--o{ dataset_artifact_features : "set null"
    feature_sets |o--o{ dataset_artifact_features : "source_feature_set_id (set null)"
    dataset_artifacts ||--o{ dataset_artifact_feature_sets : "cascade"
    feature_sets ||--o{ dataset_artifact_feature_sets : "cascade"

    datasets {
        string dataset_id PK
        string project_id FK
        string user_id FK "UQ(project_id, dataset_name)"
    }
    dataset_artifacts {
        string artifact_id PK
        string dataset_id FK
        string parent_artifact_id FK
        string pipeline_stage "PipelineStage"
        json output_paths "C2"
        json validation_report "C1 snapshot"
    }
    features {
        string feature_id PK
        string project_id FK "UQ(project_id, feature_key)"
        string user_id FK "set null"
        string status
    }
    feature_sets {
        string feature_set_id PK
        string project_id FK "UQ(project_id, set_key)"
    }
    dataset_artifact_features {
        string artifact_id PK
        string feature_key PK
        string feature_id FK
        string source_feature_set_id FK
    }
    system_column_metadata {
        string metadata_id PK
        string column_key "unique"
        string category "CORE | DOMAIN"
        string ml_role "C1 non_ml_columns"
    }
```

`system_column_metadata` is global (no `project_id`); it is the first kind of system metadata (`P-01`).

## 3. Training & model registry — [module 3](modules/training-and-models.md)

```mermaid
erDiagram
    projects |o--o{ models : "null = built-in"
    models ||--o{ model_versions : "cascade"
    models |o--o{ training_runs : "set null"
    projects |o--o{ training_runs : "cascade"
    training_runs ||--o{ run_datasets : "cascade"
    run_datasets }o..|| dataset_artifacts : "soft: dataset_artifact_id"
    model_versions |o..o| training_runs : "soft: run_id / version_id"

    models {
        string model_id PK
        string project_id FK
        string user_id FK
    }
    model_versions {
        string version_id PK
        string model_id FK
        string project_id FK
        string user_id FK
        string semver "v1, v2 ... UQ(project_id, model_id, semver)"
        string status "ModelVersionStatus"
        string artifact_uri "C3"
    }
    training_runs {
        string run_id PK
        string project_id FK
        string user_id FK
        string model_id FK
        string status "TrainingRunStatus"
        string external_job_id "remote compute"
    }
    run_datasets {
        string id PK
        string run_id FK
        string dataset_artifact_id "soft"
    }
```

## 4. Detection & rules — [module 4](modules/detection-and-rules.md)

```mermaid
erDiagram
    projects ||--o{ rules : "cascade"
    users ||--o{ rules : "restrict"
    rules ||--o{ rule_versions : "cascade, immutable"
    projects ||--o{ detection_jobs : "cascade"
    users ||--o{ detection_jobs : "restrict"
    detection_jobs }o..o| model_versions : "soft: model_version_id"
    detection_jobs }o..o| dataset_artifacts : "soft: target_artifact_id"

    rules {
        string rule_id PK
        string project_id FK "UQ(project_id, rule_code)"
        string user_id FK
        string status "DRAFT | ACTIVE | INACTIVE"
    }
    rule_versions {
        string rule_version_id PK
        string rule_id FK
        int version_number "UQ(rule_id, version_number)"
    }
    detection_jobs {
        string job_id PK
        string project_id FK
        string user_id FK
        string status "DetectionJobStatus"
        string model_version_id "soft"
        string deployment_id "legacy, holds model_version_id"
    }
```

## 5. Investigation — [module 5](modules/investigation-and-graph.md)

```mermaid
erDiagram
    fraud_cases ||--o{ entity_blacklist : "source_case_id"
    fraud_cases }o..|| projects : "soft: project_id"
    fraud_cases }o..o| detection_jobs : "soft: detection_job_id"
    fraud_cases }o..o| model_versions : "soft: model_version_id"

    fraud_cases {
        string case_id PK
        string project_id "soft, UQ(project_id, event_id), UQ(project_id, case_code)"
        string user_id "transaction subject, NOT owner"
        string status "CaseStatus"
        int version "optimistic lock INV-012"
    }
    entity_blacklist {
        string blacklist_id PK
        string project_id "soft"
        string source_case_id FK
        string status "partial UQ when ACTIVE"
    }
    audit_logs {
        string log_id PK
        string project_id
        string entity_id "append-only"
    }
```

## 6. Insight & warehouse — [module 6](modules/insight-and-warehouse.md)

No OLTP tables. The warehouse is Parquet files (`C5`) read by DuckDB; it joins `fraud_cases` (module 5) for ground truth.
