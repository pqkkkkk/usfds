import json
from pathlib import Path
from typing import Optional
import uuid
import typer
from rich.console import Console
from rich.panel import Panel

from usfds_core.domain.entities.dataset import DatasetArtifact
from usfds_core.domain.entities.enums import PipelineStage, ValidationStatus
from usfds_core.domain.schemas.preprocessing_config import (
    CategoricalEncoderType,
    CleansingConfig,
    DimReductionConfig,
    DimReductionType,
    FeatureEngineeringConfig,
    MissingValueStrategy,
    PreprocessingConfig,
    ResamplingConfig,
    ResamplingStrategy,
    ScalerType,
    SplitConfig,
    TransformationConfig,
)
from usfds_core.services.preprocessing.feature_engineering_service import FeatureEngineeringExecutionService
from usfds_core.services.preprocessing.preprocessing_service import PreprocessingExecutionService
from usfds_infra.storage.local_storage import LocalFileStorage
from usfds_cli.utils.config_loader import dump_template_config, load_preprocessing_config
from usfds_cli.utils.renderer import console, render_artifact_summary, render_banner

app = typer.Typer(
    name="preprocess",
    help="Dataset preprocessing, temporal splitting, transformation, and feature engineering commands.",
    no_args_is_help=True,
)


@app.command("run")
def run_preprocessing(
    input_file: Path = typer.Option(
        ...,
        "--input-file",
        "-i",
        help="Path to the raw/input dataset file (CSV, Parquet, or JSON).",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to the YAML or JSON preprocessing configuration file.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    storage_dir: Path = typer.Option(
        Path("./storage"),
        "--storage-dir",
        "-s",
        help="Base directory for LocalFileStorage.",
    ),
    user_name: str = typer.Option(
        "cli_user",
        "--user-name",
        "-u",
        help="User or service initiating the preprocessing run.",
    ),
    output_report: Optional[Path] = typer.Option(
        None,
        "--output-report",
        "-o",
        help="Path to write the execution result summary JSON report.",
    ),
    # Optional direct flags (used if --config is omitted)
    time_col: str = typer.Option("Time", "--time-col", help="Name of the timestamp or sequential time column."),
    amount_col: str = typer.Option("Amount", "--amount-col", help="Name of the transaction amount column."),
    target_col: str = typer.Option("Class", "--target-col", help="Name of the fraud target label column."),
    test_size: float = typer.Option(0.2, "--test-size", help="Proportion of the dataset to include in the test split."),
    scaler: ScalerType = typer.Option(ScalerType.ROBUST, "--scaler", help="Scaling method for continuous features."),
    numeric_cols: Optional[str] = typer.Option(
        None,
        "--numeric-cols",
        help="Comma-separated list of numeric column names to scale (e.g. 'amount,avg_amount_user,shipping_distance_km').",
    ),
    categorical_cols: Optional[str] = typer.Option(
        None,
        "--categorical-cols",
        help="Comma-separated list of categorical column names to encode (e.g. 'country,bin_country,channel,merchant_category').",
    ),
    categorical_encoder: CategoricalEncoderType = typer.Option(
        CategoricalEncoderType.ONE_HOT,
        "--categorical-encoder",
        help="Encoding technique for categorical features ('one_hot', 'binary', 'ordinal').",
    ),
    feature_engineering: bool = typer.Option(
        True,
        "--feature-engineering/--no-feature-engineering",
        help="Whether to execute the feature engineering stage.",
    ),
    enable_hour_of_day: bool = typer.Option(
        True,
        "--hour-of-day/--no-hour-of-day",
        help="Extract cyclical hour of day from timestamp column.",
    ),
    enable_amount_ratios: bool = typer.Option(
        True,
        "--amount-ratios/--no-amount-ratios",
        help="Compute amount to historical mean ratios.",
    ),
    enable_velocity: bool = typer.Option(
        False,
        "--velocity/--no-velocity",
        help="Compute rolling transaction velocity features.",
    ),
    customer_id_col: Optional[str] = typer.Option(
        None,
        "--customer-id-col",
        help="Customer ID column name for velocity aggregations.",
    ),
    resampling: ResamplingStrategy = typer.Option(
        ResamplingStrategy.NONE, "--resampling", help="Resampling strategy for handling imbalanced data."
    ),
    dim_reduction: DimReductionType = typer.Option(
        DimReductionType.NONE, "--dim-reduction", help="Dimensionality reduction technique."
    ),
    n_components: Optional[int] = typer.Option(10, "--n-components", help="Number of components for PCA."),
    k_features: Optional[int] = typer.Option(15, "--k-features", help="Top K features to select for SelectKBest."),
    drop_duplicates: bool = typer.Option(True, "--drop-duplicates/--no-drop-duplicates", help="Whether to remove duplicate rows."),
    missing_strategy: MissingValueStrategy = typer.Option(
        MissingValueStrategy.DROP, "--missing-strategy", help="Strategy for handling missing values."
    ),
    outlier_clipping: bool = typer.Option(False, "--outlier-clipping/--no-outlier-clipping", help="Whether to enable percentile-based outlier clipping."),
):
    """Executes the end-to-end preprocessing pipeline on the input dataset."""
    render_banner()

    storage = LocalFileStorage(base_dir=storage_dir)

    # 1. Determine input file storage path
    resolved_input = input_file.resolve()
    input_storage_path = str(resolved_input)

    # 2. Build or load PreprocessingConfig
    if config_file is not None:
        console.print(f"[cyan][INFO] Loading configuration from:[/cyan] [bold]{config_file}[/bold]")
        config = load_preprocessing_config(config_file)
    else:
        console.print("[cyan][INFO] Constructing configuration from CLI arguments...[/cyan]")
        num_columns = [c.strip() for c in numeric_cols.split(",") if c.strip()] if numeric_cols else []
        cat_columns = [c.strip() for c in categorical_cols.split(",") if c.strip()] if categorical_cols else []

        fe_hour = enable_hour_of_day if feature_engineering else False
        fe_ratios = enable_amount_ratios if feature_engineering else False
        fe_velocity = enable_velocity if feature_engineering else False

        config = PreprocessingConfig(
            cleansing=CleansingConfig(
                drop_duplicates=drop_duplicates,
                missing_value_strategy=missing_strategy,
                outlier_clipping=outlier_clipping,
            ),
            split=SplitConfig(
                time_column=time_col,
                target_column=target_col,
                test_size=test_size,
            ),
            feature_engineering=FeatureEngineeringConfig(
                time_col=time_col,
                amount_col=amount_col,
                enable_hour_of_day=fe_hour,
                enable_amount_ratios=fe_ratios,
                enable_velocity_features=fe_velocity,
                customer_id_col=customer_id_col,
            ),
            transformation=TransformationConfig(
                numeric_columns=num_columns,
                categorical_columns=cat_columns,
                scaler=scaler,
                categorical_encoder=categorical_encoder,
            ),
            dim_reduction=DimReductionConfig(
                method=dim_reduction,
                n_components=n_components,
                k_features=k_features,
            ),
            resampling=ResamplingConfig(
                method=resampling,
                sampling_strategy="auto",
                random_state=42,
            ),
        )

    # 3. Create parent DatasetArtifact representing the input file
    dataset_id = uuid.uuid4()
    parent_artifact = DatasetArtifact(
        artifact_id=uuid.uuid4(),
        dataset_id=dataset_id,
        parent_artifact_id=None,
        pipeline_stage=PipelineStage.MAPPED,
        storage_path=str(input_file.parent.resolve()),
        output_paths={"mapped": input_storage_path},
        validation_status=ValidationStatus.PASSED,
        created_by=user_name,
    )

    # 4. Execute end-to-end preprocessing pipeline with progress animation
    fe_service = FeatureEngineeringExecutionService(file_storage=storage)
    prep_service = PreprocessingExecutionService(file_storage=storage)
    with console.status("[bold green]Executing Preprocessing Pipeline...[/bold green]", spinner="dots"):
        try:
            fe_artifact = fe_service.execute(
                parent_artifact=parent_artifact,
                config=config.feature_engineering,
                user_name=user_name,
            )
            processed_artifact = prep_service.execute(
                parent_artifact=fe_artifact,
                config=config,
                user_name=user_name,
            )
        except Exception as e:
            console.print(f"[bold red]✗ Error during preprocessing execution:[/bold red] {e}")
            raise typer.Exit(code=1)

    # 5. Optionally dump JSON report
    report_path_str = None
    if output_report is not None:
        report_data = {
            "artifact_id": str(processed_artifact.artifact_id),
            "dataset_id": str(processed_artifact.dataset_id),
            "parent_artifact_id": str(processed_artifact.parent_artifact_id),
            "pipeline_stage": processed_artifact.pipeline_stage.value,
            "storage_path": processed_artifact.storage_path,
            "output_paths": processed_artifact.output_paths,
            "checksum_sha256": processed_artifact.checksum_sha256,
            "row_count": processed_artifact.row_count,
            "column_count": processed_artifact.column_count,
            "validation_status": processed_artifact.validation_status.value,
            "validation_report": processed_artifact.validation_report,
            "created_by": processed_artifact.created_by,
            "created_at": processed_artifact.created_at.isoformat(),
        }
        output_report.parent.mkdir(parents=True, exist_ok=True)
        output_report.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
        report_path_str = str(output_report.resolve())

    # 6. Render final summary
    render_artifact_summary(processed_artifact, output_report_path=report_path_str)


@app.command("template")
def generate_config_template(
    output_file: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Path to write the template configuration file (default: prints to stdout).",
    ),
    fmt: str = typer.Option(
        "yaml",
        "--format",
        "-f",
        help="Template format: 'yaml' or 'json'.",
    ),
):
    """Generates a starter preprocessing configuration template in YAML or JSON format."""
    template_content = dump_template_config(output_path=output_file, fmt=fmt)
    if output_file is None:
        console.print(template_content)
    else:
        console.print(f"[bold green][OK] Preprocessing template generated at:[/bold green] [underline]{output_file.resolve()}[/underline]")


@app.command("validate-config")
def validate_config(
    config_file: Path = typer.Argument(
        ...,
        help="Path to the preprocessing configuration file to validate.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
):
    """Validates a preprocessing configuration YAML/JSON file against the domain schema."""
    try:
        config = load_preprocessing_config(config_file)
        console.print(f"[bold green][OK] Configuration file is VALID:[/bold green] {config_file.resolve()}")
        console.print(Panel(json.dumps(config.model_dump(mode="json"), indent=2), title="Parsed Configuration"))
    except Exception as e:
        console.print(f"[bold red][ERROR] Configuration validation FAILED:[/bold red] {e}")
        raise typer.Exit(code=1)
