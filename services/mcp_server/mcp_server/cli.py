"""JSON command-line interface for the local product-review workflow."""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from requests import RequestException

from .tools import api, drafts, preparation, review, submission, workspace
from .tools.validation import validate_product_draft


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="baboom-review")
    result.add_argument("--env-file", type=Path)
    commands = result.add_subparsers(dest="command", required=True)
    queue = commands.add_parser("queue", help="List work without reserving it")
    queue.add_argument("--status", default="queued")
    queue.add_argument("--search", default="")
    queue.add_argument("--limit", type=int, default=20)
    checkout = commands.add_parser("checkout", help="Reserve queued work")
    checkout.add_argument("--item-id", type=int)
    resume = commands.add_parser(
        "resume", help="Reload a review and preserve local edits"
    )
    resume.add_argument("item_id", type=int)
    for name in (
        "show",
        "prepare",
        "draft",
        "validate",
        "heartbeat",
        "release",
        "ignore",
    ):
        commands.add_parser(name)
    update = commands.add_parser("update-draft", help="Apply a local JSON patch file")
    update.add_argument("file", type=Path)
    candidates = commands.add_parser("candidates", help="Search for existing products")
    candidates.add_argument("--search", default="")
    candidates.add_argument("--ean", default="")
    candidates.add_argument("--limit", type=int, default=20)
    choices = commands.add_parser("choices", help="List catalog reference IDs")
    choices.add_argument("kind", choices=("brands", "categories", "tags"))
    choices.add_argument("--search", default="")
    choices.add_argument("--limit", type=int, default=50)
    submit = commands.add_parser("submit", help="Preview staging; --confirm sends it")
    submit.add_argument("--confirm", action="store_true")
    approve = commands.add_parser(
        "approve", help="Preview approval; --confirm applies it"
    )
    target = approve.add_mutually_exclusive_group(required=True)
    target.add_argument("--product-id", type=int)
    target.add_argument(
        "--create-product", type=Path, help="Approved catalog fields in JSON"
    )
    approve.add_argument("--confirm", action="store_true")
    error = commands.add_parser("report-error")
    error.add_argument("message")
    error.add_argument("--fatal", action="store_true")
    return result


def _read_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("O arquivo deve conter um objeto JSON.")
    return value


def execute(args: argparse.Namespace) -> object:
    local = {
        "show": workspace.get_current_item,
        "draft": drafts.load_draft,
        "validate": lambda: validate_product_draft(drafts.load_draft()),
        "prepare": lambda: preparation.build_prepared_context(
            workspace.get_current_item()
        ),
    }
    if args.command in local:
        return local[args.command]()
    if args.command in {"heartbeat", "release", "ignore"}:
        return review.act_on_current_item(args.command)
    return _execute_remote(args)


def _execute_remote(args: argparse.Namespace) -> object:
    match args.command:
        case "queue":
            return api.review_queue(args.status, args.search, args.limit)
        case "checkout":
            return review.checkout_item(args.item_id)
        case "resume":
            return review.resume_item(args.item_id)
        case "update-draft":
            return drafts.update_draft(_read_object(args.file))
        case "candidates":
            return api.catalog_candidates(args.search, args.ean, args.limit)
        case "choices":
            return api.catalog_choices(args.kind, args.search, args.limit)
        case "submit":
            return _submit(args)
        case "approve":
            return _approve(args)
        case "report-error":
            return review.report_current_item_error(args.message, args.fatal)
    raise ValueError("Comando desconhecido.")


def _submit(args: argparse.Namespace) -> dict:
    if not args.confirm:
        return {
            "preview": submission.build_submission_preview(),
            "confirmationRequired": True,
        }
    return submission.submit_draft(confirm=True)


def _approve(args: argparse.Namespace) -> dict:
    return review.approve_current_item(
        product_id=args.product_id,
        create_product=_read_object(args.create_product)
        if args.create_product
        else None,
        confirm=args.confirm,
    )


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    load_dotenv(args.env_file or Path(__file__).resolve().parents[1] / ".env")
    try:
        result = execute(args)
    except (OSError, ValueError, RuntimeError, RequestException) as exc:
        sys.stderr.write(
            json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False) + "\n"
        )
        return 1
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    if isinstance(result, dict) and result.get("ok") is False:
        return int(not result.get("confirmationRequired"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
