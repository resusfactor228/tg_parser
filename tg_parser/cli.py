import asyncio
from typing import List

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

from .client import build_client, connect_phone, connect_qr
from .groups import get_groups
from .members import fetch_members, fetch_bios
from .exporter import export
from .models import GroupInfo

console = Console()


def _print_groups_table(groups: List[GroupInfo]) -> None:
    table = Table(title="Ваши группы", show_lines=True)
    table.add_column("#", style="bold cyan", width=4)
    table.add_column("Название", style="bold white")
    table.add_column("Участников", justify="right", style="green")
    table.add_column("Тип", style="dim")

    for i, g in enumerate(groups, 1):
        count = str(g.members_count) if g.members_count else "?"
        gtype = "Супергруппа" if g.is_supergroup else "Группа"
        table.add_row(str(i), g.title, count, gtype)

    console.print(table)


def _parse_selection(raw: str, total: int) -> List[int]:
    if raw.strip().lower() == "all":
        return list(range(total))

    indices = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < total:
                indices.append(idx)
    return indices


async def run() -> None:
    console.rule("[bold blue]Telegram Group Parser")

    client = build_client()

    await client.connect()
    if not await client.is_user_authorized():
        method = console.input(
            "[bold]Метод входа:[/bold] [[cyan]1[/cyan]] QR-код  [[cyan]2[/cyan]] Номер телефона → "
        ).strip()
        if method == "2":
            await connect_phone(client)
        else:
            await connect_qr(client)

    me = await client.get_me()
    console.print(f"[green]Авторизован как:[/green] {me.first_name} (@{me.username})")

    with console.status("Загрузка списка групп..."):
        groups = await get_groups(client)

    if not groups:
        console.print("[yellow]Групп не найдено.[/yellow]")
        await client.disconnect()
        return

    _print_groups_table(groups)

    raw = console.input(
        "\n[bold]Введите номера групп для парсинга[/bold] (например: [cyan]1,3,5[/cyan] или [cyan]all[/cyan]): "
    )
    indices = _parse_selection(raw, len(groups))

    if not indices:
        console.print("[red]Ничего не выбрано. Выход.[/red]")
        await client.disconnect()
        return

    selected = [groups[i] for i in indices]

    fetch_bio_answer = console.input(
        "\n[bold]Собирать bio (описание профиля)?[/bold] Это медленно (~2с/чел) [y/[cyan]N[/cyan]]: "
    )
    fetch_bio = fetch_bio_answer.strip().lower() == "y"

    if fetch_bio:
        console.print("[yellow]Bio будет собрано. Для больших групп (>500 чел) это займёт много времени.[/yellow]")

    # Итоговая сводка
    summary_rows = []

    for group in selected:
        console.rule(f"[bold]{group.title}[/bold]")
        records = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed} участников"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Загрузка участников...", total=group.members_count or 1000)

            async def on_member_progress(count: int) -> None:
                progress.update(task, completed=count)

            records = await fetch_members(client, group, on_progress=on_member_progress)
            progress.update(task, completed=len(records), total=len(records))

        console.print(f"  Найдено участников: [bold green]{len(records)}[/bold green]")

        if fetch_bio and records:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total}"),
                TimeElapsedColumn(),
                console=console,
            ) as bio_progress:
                bio_task = bio_progress.add_task("Загрузка bio...", total=len(records))

                async def on_bio_progress(done: int, total: int) -> None:
                    bio_progress.update(bio_task, completed=done, total=total)

                await fetch_bios(client, records, group.id, on_progress=on_bio_progress)

        csv_path, json_path = export(records, group.id, group.title)
        summary_rows.append((group.title, len(records), csv_path, json_path))
        console.print(f"  CSV:  [dim]{csv_path}[/dim]")
        console.print(f"  JSON: [dim]{json_path}[/dim]")

    # Итоговая таблица
    console.rule("[bold green]Готово")
    summary = Table(show_lines=True)
    summary.add_column("Группа", style="bold white")
    summary.add_column("Участников", justify="right", style="green")
    summary.add_column("CSV", style="dim")
    summary.add_column("JSON", style="dim")

    for title, count, csv_p, json_p in summary_rows:
        summary.add_row(title, str(count), csv_p, json_p)

    console.print(summary)
    await client.disconnect()
