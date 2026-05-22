"""envlint command-line interface (Typer + Rich)."""

from __future__ import annotations

import contextlib
import os
import sys
from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from . import __version__
from .diff import diff_envs
from .generate import generate_example, generate_schema
from .lint import lint as run_lint
from .parser import EnvFileTooLargeError, ParsedEnv, parse_file
from .report import Report, Severity
from .schema import Schema, find_schema, load_schema
from .schema import validate as run_validate
from .secrets import scan as run_secret_scan

app = typer.Typer(
    name="envlint",
    help="Lint, validate, and document your .env files.",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# On legacy Windows consoles the default code page (e.g. cp1252) cannot encode
# some characters and would crash on write. Switch the streams to UTF-8 where
# the runtime supports it so output is robust cross-platform.
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        with contextlib.suppress(ValueError, OSError):  # pragma: no cover - platform dependent
            _reconfigure(encoding="utf-8", errors="replace")


def _make_out_console() -> Console:
    """Build the stdout console.

    When output is an interactive terminal, let Rich auto-detect the width so
    the table fits the user's window. When it is a pipe/CI/test capture, Rich
    would otherwise fall back to 80 columns and truncate rule codes and
    messages, so we pin a generous width to keep findings readable/greppable.
    """
    if sys.stdout.isatty():
        return Console()
    env_cols = os.environ.get("COLUMNS")
    width = max(int(env_cols), 140) if (env_cols and env_cols.isdigit()) else 140
    return Console(width=width)


# stdout for results, stderr for diagnostics so JSON stays clean on stdout.
out = _make_out_console()
err = Console(stderr=True)

# Exit codes
EXIT_OK = 0
EXIT_PROBLEMS = 1
EXIT_USAGE = 2


class OutputFormat(str, Enum):
    text = "text"
    json = "json"


def _version_callback(value: bool) -> None:
    if value:
        out.print(f"envlint {__version__}")
        raise typer.Exit(EXIT_OK)


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show the version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """envlint: catch missing vars, leaked secrets, and typos in your .env files."""


_SEV_STYLE = {
    Severity.ERROR: "bold red",
    Severity.WARNING: "yellow",
    Severity.INFO: "cyan",
}
_SEV_LABEL = {
    Severity.ERROR: "error",
    Severity.WARNING: "warn",
    Severity.INFO: "info",
}


def _render_text(report: Report, *, quiet: bool) -> None:
    findings = report.sorted()
    if not findings:
        if not quiet:
            out.print("[bold green]All checks passed.[/] No problems found.")
        return

    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("Location", style="dim", overflow="fold")
    table.add_column("Level", no_wrap=True)
    table.add_column("Rule", style="dim", no_wrap=True)
    table.add_column("Message", overflow="fold")

    for f in findings:
        loc = f.file or "?"
        if f.line:
            loc = f"{loc}:{f.line}"
        level = Text(_SEV_LABEL[f.severity], style=_SEV_STYLE[f.severity])
        msg = Text(f.message)
        if f.hint:
            msg.append(f"\n  -> {f.hint}", style="dim italic")
        table.add_row(loc, level, f.code, msg)

    out.print(table)
    out.print()
    summary = (
        f"[bold red]{len(report.errors)} error(s)[/], "
        f"[yellow]{len(report.warnings)} warning(s)[/], "
        f"[cyan]{len(report.infos)} info[/]"
    )
    out.print(summary)


def _parse_or_exit(path: Path) -> ParsedEnv:
    if not path.exists():
        err.print(f"[bold red]error:[/] file not found: {path}")
        raise typer.Exit(EXIT_USAGE)
    try:
        return parse_file(path)
    except EnvFileTooLargeError as exc:
        err.print(f"[bold red]error:[/] {exc}")
        raise typer.Exit(EXIT_USAGE) from exc
    except OSError as exc:  # pragma: no cover - filesystem edge
        err.print(f"[bold red]error:[/] cannot read {path}: {exc}")
        raise typer.Exit(EXIT_USAGE) from exc


def _load_schema_or_exit(
    schema_path: Optional[Path], env_path: Path, *, no_schema: bool
) -> Optional[Schema]:
    if no_schema:
        return None
    if schema_path is not None:
        if not schema_path.exists():
            err.print(f"[bold red]error:[/] schema not found: {schema_path}")
            raise typer.Exit(EXIT_USAGE)
        chosen = schema_path
    else:
        found = find_schema(env_path)
        if found is None:
            return None
        chosen = found
    try:
        return load_schema(chosen)
    except (ValueError, OSError) as exc:
        err.print(f"[bold red]error:[/] invalid schema {chosen}: {exc}")
        raise typer.Exit(EXIT_USAGE) from exc


@app.command()
def check(
    paths: list[Path] = typer.Argument(
        None,
        help="One or more .env files to check. Defaults to .env",
    ),
    schema: Optional[Path] = typer.Option(
        None, "--schema", "-s", help="Path to a .env.schema (TOML/JSON). Auto-detected if omitted."
    ),
    strict: bool = typer.Option(
        False, "--strict", help="Treat warnings as errors (non-zero exit on any warning)."
    ),
    no_secrets: bool = typer.Option(False, "--no-secrets", help="Skip secret detection."),
    no_schema: bool = typer.Option(False, "--no-schema", help="Skip schema validation."),
    no_lint: bool = typer.Option(False, "--no-lint", help="Skip structural lint rules."),
    fmt: OutputFormat = typer.Option(
        OutputFormat.text, "--format", "-f", help="Output format."
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Only print problems."),
) -> None:
    """Lint and validate .env file(s). Exits non-zero when problems are found."""
    targets = paths or [Path(".env")]
    report = Report()

    for path in targets:
        env = _parse_or_exit(path)
        loaded_schema = _load_schema_or_exit(schema, path, no_schema=no_schema)

        if not no_lint:
            report.extend(run_lint(env))

        if loaded_schema is not None:
            report.extend(run_validate(env, loaded_schema))

        if not no_secrets:
            secret_keys = loaded_schema.secret_keys if loaded_schema else set()
            nonsecret_keys = loaded_schema.nonsecret_keys if loaded_schema else set()
            report.extend(
                run_secret_scan(
                    env, secret_keys=secret_keys, nonsecret_keys=nonsecret_keys
                )
            )

    has_problems = report.has_problems(strict=strict)
    exit_code = EXIT_PROBLEMS if has_problems else EXIT_OK

    if fmt is OutputFormat.json:
        out.print_json(report.to_json(exit_code=exit_code))
    else:
        _render_text(report, quiet=quiet)

    raise typer.Exit(exit_code)


@app.command()
def example(
    env_file: Path = typer.Argument(Path(".env"), help="Source .env file."),
    output: Optional[Path] = typer.Option(
        None, "--out", "-o", help="Write to this file instead of stdout."
    ),
    schema: Optional[Path] = typer.Option(
        None, "--schema", "-s", help="Schema to enrich the example with descriptions."
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite the output file if it exists."),
) -> None:
    """Generate a redacted [bold].env.example[/] from a .env file."""
    env = _parse_or_exit(env_file)
    loaded_schema = _load_schema_or_exit(schema, env_file, no_schema=False)
    content = generate_example(env, schema=loaded_schema)

    if output is None:
        out.print(content, end="", markup=False, highlight=False)
        raise typer.Exit(EXIT_OK)

    if output.exists() and not force:
        err.print(f"[bold red]error:[/] {output} exists; use --force to overwrite.")
        raise typer.Exit(EXIT_USAGE)
    output.write_text(content, encoding="utf-8")
    err.print(f"[green]Wrote[/] {output}")
    raise typer.Exit(EXIT_OK)


@app.command()
def schema(  # noqa: F811 - intentional command name
    env_file: Path = typer.Argument(Path(".env"), help="Source .env file."),
    output: Optional[Path] = typer.Option(
        None, "--out", "-o", help="Write to this file instead of stdout."
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite the output file if it exists."),
) -> None:
    """Scaffold a [bold].env.schema[/] (TOML) from an existing .env file."""
    env = _parse_or_exit(env_file)
    content = generate_schema(env)

    if output is None:
        out.print(content, end="", markup=False, highlight=False)
        raise typer.Exit(EXIT_OK)

    if output.exists() and not force:
        err.print(f"[bold red]error:[/] {output} exists; use --force to overwrite.")
        raise typer.Exit(EXIT_USAGE)
    output.write_text(content, encoding="utf-8")
    err.print(f"[green]Wrote[/] {output}")
    raise typer.Exit(EXIT_OK)


@app.command()
def diff(
    a: Path = typer.Argument(..., help="First .env file."),
    b: Path = typer.Argument(..., help="Second .env file."),
    values: bool = typer.Option(
        False, "--values", help="Show differing values (may reveal secrets)."
    ),
) -> None:
    """Diff two .env files: keys only in each, and keys whose values differ."""
    env_a = _parse_or_exit(a)
    env_b = _parse_or_exit(b)
    result = diff_envs(env_a, env_b)

    if not result.has_differences:
        out.print("[bold green]No differences.[/] Both files declare the same keys and values.")
        raise typer.Exit(EXIT_OK)

    if result.only_in_a:
        out.print(f"[bold]Only in {a}:[/]")
        for k in result.only_in_a:
            out.print(f"  [green]+[/] {k}")
    if result.only_in_b:
        out.print(f"[bold]Only in {b}:[/]")
        for k in result.only_in_b:
            out.print(f"  [red]-[/] {k}")
    if result.changed:
        out.print("[bold]Different values:[/]")
        for k, (va, vb) in result.changed.items():
            if values:
                out.print(f"  [yellow]~[/] {k}: {va!r} -> {vb!r}")
            else:
                out.print(f"  [yellow]~[/] {k} (values differ; pass --values to show)")

    # diff is informational; exit 0 even when there are differences.
    raise typer.Exit(EXIT_OK)


def run() -> None:  # pragma: no cover - module entry helper
    app()


if __name__ == "__main__":  # pragma: no cover
    run()
