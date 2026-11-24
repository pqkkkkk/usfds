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


class DetectionJobStatus(StrEnum):
    """Lifecycle status of a batch fraud detection job execution."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class InvestigationStatus(StrEnum):
    """Lifecycle and resolution status of a fraud case investigation."""
    PENDING = "PENDING"
    UNDER_INVESTIGATION = "UNDER_INVESTIGATION"
    CONFIRMED_FRAUD = "CONFIRMED_FRAUD"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    CLOSED = "CLOSED"

class LogicalOperator(StrEnum):
    AND = "AND"
    OR = "OR"

class ComparisonOperator(StrEnum):
    EQUALS = "=="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    GREATER_THAN_OR_EQUAL = ">="
    LESS_THAN = "<"
    LESS_THAN_OR_EQUAL = "<="
    IN = "IN"
    NOT_IN = "NOT_IN"
    CONTAINS = "CONTAINS"
    REGEX = "REGEX"
    EXISTS = "EXISTS"

class RuleAction(StrEnum):
    REJECT = "REJECT"           
    REVIEW = "REVIEW"                     
    ALLOW = "ALLOW"                

class RuleStatus(StrEnum):
    DRAFT = "DRAFT"              
    ACTIVE = "ACTIVE"            
    INACTIVE = "INACTIVE"        


class ProjectStatus(StrEnum):
    """Lifecycle status of a fraud detection project."""
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class LogicalDataType(StrEnum):
    """Logical data type groups for project-level RAW schema governance."""
    NUMERIC = "NUMERIC"
    STRING = "STRING"
    BOOLEAN = "BOOLEAN"
    DATETIME = "DATETIME"


class UserStatus(StrEnum):
    """Lifecycle status of a user account."""
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class RoleScope(StrEnum):
    """Scope level where a role can be assigned."""
    SYSTEM = "SYSTEM"
    PROJECT = "PROJECT"


class GrantScope(StrEnum):
    """Effective permission grant scope."""
    OWN = "OWN"
    PROJECT = "PROJECT"
    SYSTEM = "SYSTEM"


class AuthMode(StrEnum):
    """Authentication enforcement mode."""
    LOCAL_AUTO = "local_auto"
    REQUIRED = "required"


class ColumnCategory(StrEnum):
    """Category of a canonical system column."""
    CORE = "CORE"
    DOMAIN = "DOMAIN"


class ColumnMlRole(StrEnum):
    """Machine learning role of a canonical column."""
    FEATURE = "FEATURE"
    IDENTIFIER = "IDENTIFIER"
    TIMESTAMP = "TIMESTAMP"
    LABEL = "LABEL"


class FeatureMegafamily(StrEnum):
    """Fraud domain megafamilies organizing all built-in and custom features."""
    ORDERS = "ORDERS"
    MONETARY = "MONETARY"
    IDENTITY = "IDENTITY"
    PAYMENT = "PAYMENT"
    LOCATIONS = "LOCATIONS"
    NETWORK = "NETWORK"


class FeatureComputeKind(StrEnum):
    """Execution tier/engine for a feature definition stored in DB."""
    VELOCITY = "VELOCITY"
    EXPRESSION = "EXPRESSION"
    TARGET_RATE = "TARGET_RATE"
    PYTHON_CODE = "PYTHON_CODE"


class FeatureStatus(StrEnum):
    """Lifecycle status of a feature definition."""
    ACTIVE = "ACTIVE"
    DRAFT = "DRAFT"
    ARCHIVED = "ARCHIVED"


class SemanticColumnType(StrEnum):
    """Optional semantic column types used to bind raw/optional columns to Domain features."""
    EVENT_ID = "EVENT_ID"
    TIMESTAMP = "TIMESTAMP"
    AMOUNT = "AMOUNT"
    USER_ID = "USER_ID"
    LABEL = "LABEL"
    MERCHANT = "MERCHANT"
    CATEGORY = "CATEGORY"
    DEVICE_ID = "DEVICE_ID"
    IP_ADDRESS = "IP_ADDRESS"
    EMAIL = "EMAIL"
    PHONE_NUMBER = "PHONE_NUMBER"
    CARD_ID = "CARD_ID"
    CARD_BIN = "CARD_BIN"
    COUNTRY = "COUNTRY"
    BIN_COUNTRY = "BIN_COUNTRY"
    CURRENCY = "CURRENCY"
    CHANNEL = "CHANNEL"
    LAT = "LAT"
    LONG = "LONG"
    MERCH_LAT = "MERCH_LAT"
    MERCH_LONG = "MERCH_LONG"
    BILLING_ZIP = "BILLING_ZIP"
    USER_AGENT = "USER_AGENT"
