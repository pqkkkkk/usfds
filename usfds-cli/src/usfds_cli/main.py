import typer

from usfds_cli.commands.preprocess import app as preprocess_app
from usfds_cli.utils.renderer import render_banner

app = typer.Typer(
    name="usfds",
    help="USFDS - Unified Stream Fraud Detection System CLI",
    no_args_is_help=True,
    add_completion=False,
)

# Register sub-command groups
app.add_typer(preprocess_app, name="preprocess")


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context):
    """Main callback to render the banner when appropriate."""
    if ctx.invoked_subcommand is None:
        render_banner()


if __name__ == "__main__":
    app()
