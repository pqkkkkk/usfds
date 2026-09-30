"""Configuration settings and path resolution for USFDS Agent."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Workspace Root Discovery: points to the root repo 'usfds' containing storage_output
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Load environment variables from both root and local .env
load_dotenv(REPO_ROOT / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()

# Default Storage Output Paths
STORAGE_OUTPUT = REPO_ROOT / "storage_output"

TEST_ENRICHED_PATH = (
    STORAGE_OUTPUT
    / "datasets"
    / "bf842480-4581-4cf2-bccc-fc2f540ddfce"
    / "artifacts"
    / "f4b0bb1a-b7a4-4f5e-b856-78cd5054d49f"
    / "test_enriched.parquet"
)

EVAL_PREDICTIONS_PATH = (
    STORAGE_OUTPUT
    / "models"
    / "b43d7c31-2cc4-4fb1-9369-cdb42d5abc01"
    / "runs"
    / "47b106ec-388b-44db-83d3-a8d7c7e711df"
    / "eval_predictions.parquet"
)

TEST_PROCESSED_PATH = (
    STORAGE_OUTPUT
    / "datasets"
    / "bf842480-4581-4cf2-bccc-fc2f540ddfce"
    / "artifacts"
    / "d9bb0c4f-0f7c-4d51-9fd3-cbbe9e7c18fd"
    / "test_processed.parquet"
)

MODEL_ARTIFACT_PATH = (
    STORAGE_OUTPUT
    / "models"
    / "b43d7c31-2cc4-4fb1-9369-cdb42d5abc01"
    / "runs"
    / "47b106ec-388b-44db-83d3-a8d7c7e711df"
    / "model.joblib"
)

PIPELINE_ARTIFACT_PATH = (
    STORAGE_OUTPUT
    / "datasets"
    / "bf842480-4581-4cf2-bccc-fc2f540ddfce"
    / "artifacts"
    / "d9bb0c4f-0f7c-4d51-9fd3-cbbe9e7c18fd"
    / "fitted_pipeline.joblib"
)

# API Keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
