from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from usfds_core.domain.entities.dataset import DatasetArtifact

console = Console(safe_box=True)


def render_banner():
    """Renders the USFDS CLI banner."""
    console.print(
        Panel.fit(
            "[bold cyan]Unified Stream Fraud Detection System (USFDS)[/bold cyan]\n"
            "[dim]Data Preprocessing & Transformation CLI[/dim]",
            border_style="bright_blue",
        )
    )


def render_artifact_summary(artifact: DatasetArtifact, output_report_path: Optional[str] = None):
    """Renders a detailed summary table of the generated Preprocessing DatasetArtifact."""
    table = Table(title="[bold green]Preprocessing Execution Result[/bold green]", show_header=True, header_style="bold magenta")
    table.add_column("Property", style="cyan", width=25)
    table.add_column("Details", style="white")

    table.add_row("Artifact ID", str(artifact.artifact_id))
    table.add_row("Dataset ID", str(artifact.dataset_id))
    table.add_row("Parent Artifact ID", str(artifact.parent_artifact_id or "None (Root)"))
    table.add_row("Pipeline Stage", f"[bold yellow]{artifact.pipeline_stage.value}[/bold yellow]")
    table.add_row("Validation Status", f"[bold green]{artifact.validation_status.value}[/bold green]" if artifact.validation_status.value == "PASSED" else f"[bold yellow]{artifact.validation_status.value}[/bold yellow]")
    table.add_row("Train Rows (Processed)", f"{artifact.row_count:,}" if artifact.row_count is not None else "N/A")
    table.add_row("Column Count (Processed)", str(artifact.column_count or "N/A"))
    table.add_row("Train Data Storage Path", f"[bold green]{artifact.storage_path}[/bold green]")
    table.add_row("Test Data Storage Path", f"[bold green]{artifact.test_storage_path or 'N/A'}[/bold green]")
    table.add_row("Fitted Pipeline Storage Path", f"[bold green]{artifact.pipeline_artifact_path or 'N/A'}[/bold green]")
    table.add_row("SHA-256 Checksum", str(artifact.checksum_sha256 or "N/A"))
    table.add_row("Created By", str(artifact.created_by or "system"))
    table.add_row("Created At", artifact.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"))

    console.print(table)

    if artifact.validation_report:
        report_table = Table(title="[bold blue]Cleansing & Validation Metrics[/bold blue]", show_header=True, header_style="bold blue")
        report_table.add_column("Metric", style="cyan", width=25)
        report_table.add_column("Value", style="white")

        for k, v in artifact.validation_report.items():
            report_table.add_row(str(k), str(v))

        console.print(report_table)

    if output_report_path:
        console.print(f"[bold green][SUCCESS] Report saved successfully to:[/bold green] [underline]{output_report_path}[/underline]")
