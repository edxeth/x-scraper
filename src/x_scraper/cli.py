"""CLI interface for X/Twitter scraper using Typer."""

from __future__ import annotations

import json
import sys
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from x_scraper.bird_client import BirdClient, BirdError, BirdNotFoundError
from x_scraper.cookie_extractor import (
    extract_cookies_via_bird,
    get_best_cookies,
    manual_cookie_instructions,
    save_cookies,
    XCookies,
)
from x_scraper.models import get_settings
from x_scraper.scraper import scrape_tweets, scrape_urls
from x_scraper.utils import (
    configure_logging,
    format_results_as_markdown,
    format_tweet_as_markdown,
    generate_batch_output_path,
)

app = typer.Typer(
    name="x-scraper",
    help="Scrape tweets from X/Twitter with images and videos",
    no_args_is_help=True,
)
console = Console()


class OutputFormat(str, Enum):
    """Output format options."""

    json = "json"
    markdown = "markdown"
    md = "md"  # Alias for markdown


@app.command()
def scrape(
    urls: Annotated[
        list[str],
        typer.Argument(help="Tweet URLs to scrape"),
    ],
    output: Annotated[
        Optional[Path],
        typer.Option(
            "--output",
            "-o",
            help="Output file path (extension determines format if --format not specified)",
        ),
    ] = None,
    format: Annotated[
        OutputFormat,
        typer.Option(
            "--format",
            "-f",
            help="Output format: json or markdown",
            case_sensitive=False,
        ),
    ] = OutputFormat.json,
    parallel: Annotated[
        int,
        typer.Option(
            "--parallel",
            "-p",
            help="Number of parallel workers",
        ),
    ] = 5,
    proxy: Annotated[
        Optional[str],
        typer.Option(
            "--proxy",
            help="SOCKS5 proxy URL (e.g., socks5://user:pass@host:port)",
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logging",
        ),
    ] = False,
) -> None:
    """Scrape one or more tweet URLs.

    Examples:
        x-scraper scrape https://x.com/user/status/123
        x-scraper scrape url1 url2 url3 --parallel 10
        x-scraper scrape url1 --format markdown -o tweets.md
        x-scraper scrape url1 --proxy socks5://user:pass@host:port
    """
    # Configure logging
    log_level = "DEBUG" if verbose else "INFO"
    configure_logging(log_level)

    # Determine output format and file
    is_markdown = format in (OutputFormat.markdown, OutputFormat.md)
    if output is None:
        ext = "md" if is_markdown else "json"
        output = generate_batch_output_path(urls, ext)

    console.print(f"[bold blue]Scraping {len(urls)} tweet(s)...[/]")

    # Check Bird installation
    try:
        client = BirdClient()
        version = client.get_version()
        console.print(f"[dim]Using Bird CLI {version}[/]")
    except BirdNotFoundError as e:
        console.print(f"[red]Error: {e}[/]")
        raise typer.Exit(1)

    # Check authentication
    cookies = get_best_cookies()
    if cookies:
        console.print("[green]✓ Authentication configured[/]")
    else:
        console.print("[yellow]⚠ No cookies found. Bird will attempt auto-detection.[/]")

    # Run scraper with progress
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scraping tweets...", total=len(urls))

        # Prepare data
        data = [{"url": url} for url in urls]

        # Run scraper
        results = scrape_tweets(data)

        progress.update(task, completed=len(urls))

    # Process results
    success_count = sum(1 for r in results if r.get("success"))
    fail_count = len(results) - success_count

    # Save results in chosen format
    output.parent.mkdir(parents=True, exist_ok=True)

    if is_markdown:
        content = format_results_as_markdown(results)
        with open(output, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str, ensure_ascii=False)

    # Display summary
    console.print()
    if success_count == len(urls):
        console.print(f"[green]✓ Successfully scraped all {success_count} tweet(s)[/]")
    else:
        console.print(
            f"[yellow]Scraped {success_count}/{len(urls)} tweets ({fail_count} failed)[/]"
        )

    console.print(f"[dim]Output saved to {output} ({format.value} format)[/]")

    # Show sample of results
    if results and results[0].get("success"):
        sample = results[0]["data"]
        console.print()
        console.print(
            Panel(
                f"[bold]@{sample.get('author_handle', 'unknown')}[/]\n\n"
                f"{sample.get('text', '')[:280]}...\n\n"
                f"[dim]Images: {len(sample.get('images', []))} | Videos: {len(sample.get('videos', []))}[/]",
                title="Sample Tweet",
                border_style="blue",
            )
        )


@app.command("check-auth")
def check_auth() -> None:
    """Check authentication status and available cookies."""
    console.print("[bold]Checking authentication...[/]\n")

    # Check Bird installation
    try:
        client = BirdClient()
        version = client.get_version()
        console.print(f"[green]✓ Bird CLI installed[/] (version {version})")
    except BirdNotFoundError:
        console.print("[red]✗ Bird CLI not installed[/]")
        console.print("  Install with: bun install -g @nicepkg/bird")
        raise typer.Exit(1)

    # Check cookies
    cookies = get_best_cookies()
    if cookies:
        if cookies.auth_token == "[bird-managed]":
            console.print("[green]✓ Bird auto-detected browser cookies[/]")
        else:
            console.print("[green]✓ Cookies configured from .env or environment[/]")
            console.print(f"  AUTH_TOKEN: {cookies.auth_token[:10]}...")
            console.print(f"  CT0: {cookies.ct0[:10]}...")
        console.print("\n[green]✓ Ready to scrape![/]")
        console.print("  Try: x-scraper read https://x.com/user/status/123")
    else:
        # Try Bird auto-detection as fallback
        console.print("[yellow]⚠ No cookies found in .env or environment[/]")
        console.print("\n[bold]Testing Bird browser auto-detection...[/]")
        result = extract_cookies_via_bird()
        if result:
            console.print("[green]✓ Bird auto-detected browser cookies[/]")
        else:
            console.print("[red]✗ Bird couldn't auto-detect cookies[/]")
            console.print("\nTo fix, either:")
            console.print("1. Login to X in Safari/Chrome/Firefox (Bird auto-detects)")
            console.print("2. Set AUTH_TOKEN and CT0 in .env file or environment")
            console.print("\nRun 'x-scraper show-cookie-help' for detailed instructions")


@app.command("show-cookie-help")
def show_cookie_help() -> None:
    """Show instructions for extracting cookies manually."""
    console.print(
        Panel(
            manual_cookie_instructions(),
            title="Cookie Extraction Instructions",
            border_style="blue",
        )
    )


@app.command("read")
def read_single(
    url: Annotated[
        str,
        typer.Argument(help="Tweet URL to read"),
    ],
    format: Annotated[
        OutputFormat,
        typer.Option(
            "--format",
            "-f",
            help="Output format: json or markdown",
            case_sensitive=False,
        ),
    ] = OutputFormat.markdown,
    raw: Annotated[
        bool,
        typer.Option(
            "--raw",
            "-r",
            help="Output raw JSON from Bird (ignores --format)",
        ),
    ] = False,
) -> None:
    """Read a single tweet and display it.

    This is a quick way to test scraping without saving to file.
    Defaults to markdown format for easy reading.

    Examples:
        x-scraper read https://x.com/user/status/123
        x-scraper read https://x.com/user/status/123 --format json
        x-scraper read https://x.com/user/status/123 --raw
    """
    from x_scraper.scraper import parse_bird_response

    try:
        client = BirdClient()
        raw_data = client.read_tweet(url)

        if raw:
            console.print_json(json.dumps(raw_data, default=str))
        elif format in (OutputFormat.markdown, OutputFormat.md):
            # Parse and format as markdown
            tweet = parse_bird_response(raw_data, url)
            result = {
                "success": True,
                "url": url,
                "data": tweet.model_dump(mode="json"),
            }
            md_output = format_tweet_as_markdown(result)
            console.print(md_output)
        else:
            # JSON format
            tweet = parse_bird_response(raw_data, url)
            console.print_json(
                json.dumps(tweet.model_dump(mode="json"), default=str, ensure_ascii=False)
            )

    except BirdError as e:
        console.print(f"[red]Error: {e}[/]")
        raise typer.Exit(1)


@app.command("version")
def version() -> None:
    """Show version information."""
    from x_scraper import __version__

    console.print(f"x-scraper version {__version__}")

    try:
        client = BirdClient()
        bird_version = client.get_version()
        console.print(f"Bird CLI version {bird_version}")
    except BirdNotFoundError:
        console.print("Bird CLI: not installed")


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
