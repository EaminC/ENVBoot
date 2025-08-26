# envboot/cli.py

# CLI for envboot: create and manage environment variables for OpenStack

import json
import typer
from .osutil import conn

app = typer.Typer(no_args_is_help=True)

@app.command()
def ping():
    """Sanity check command."""
    typer.echo("pong")

@app.command("auth-check")
def auth_check():
    """Verify OpenStack credentials work."""
    try:
        c = conn()
        proj = c.identity.get_project(c.current_project_id)
        typer.echo(f"OK project: {proj.name} ({proj.id})")
    except Exception as e:
        typer.echo(f"Auth failed: {e}")
        raise typer.Exit(1)

def main():
    app()
