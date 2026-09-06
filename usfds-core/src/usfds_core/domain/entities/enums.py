from enum import StrEnum


class PipelineStage(StrEnum):
    """Stages in the data processing and preparation pipeline."""
    RAW = "RAW"
    MAPPED = "MAPPED"
    FEATURE_ENGINEERED = "FEATURE_ENGINEERED"
    PRE_PROCESSED = "PRE_PROCESSED"


class DatasetRole(StrEnum):
    """Role of the dataset during model training and evaluation."""
    TRAIN = "TRAIN"
    VALIDATION = "VALIDATION"
    TEST = "TEST"
    INFERENCE = "INFERENCE"
    BENCHMARK = "BENCHMARK"


class ValidationStatus(StrEnum):
    """Validation and data quality check status for dataset artifacts."""
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    WARNING = "WARNING"


class DataClassification(StrEnum):
    """Data sensitivity and security classification level."""
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


class RiskLevel(StrEnum):
    """Risk assessment level of the machine learning model."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RuleType(StrEnum):
    """Type of fraud detection business rule."""
    THRESHOLD = "THRESHOLD"
    ANOMALY_SCORE = "ANOMALY_SCORE"
    BLACKLIST = "BLACKLIST"
    WHITELIST = "WHITELIST"
    COMPOSITE = "COMPOSITE"
    CUSTOM = "CUSTOM"


class TrainingRunStatus(StrEnum):
    """Lifecycle and execution status of a training run."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ExecutionType(StrEnum):
    """Execution environment and packaging mechanism of a model."""
    BUILTIN = "BUILTIN"          # Concrete class built into usfds-core
    SCRIPT = "SCRIPT"            # Independent python script executed via subprocess
    DOCKER_IMAGE = "DOCKER_IMAGE"# Containerized job (Docker / Kubernetes)


class ModelVersionStatus(StrEnum):
    """Lifecycle status of a model version in the Model Registry."""
    DRAFT = "DRAFT"
    CANDIDATE = "CANDIDATE"
    APPROVED = "APPROVED"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"


class DeploymentStatus(StrEnum):
    """Operational and serving status of a model deployment."""
    PENDING = "PENDING"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    TERMINATED = "TERMINATED"


class DeploymentEnvironment(StrEnum):
    """Target deployment environment."""
    DEVELOPMENT = "DEVELOPMENT"
    STAGING = "STAGING"
    PRODUCTION = "PRODUCTION"
