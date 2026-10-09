#!/usr/bin/env python3
"""Install a reversible static CRM rule snapshot in an existing local project.

Dry-run is the default. This does not connect chats, update a drafting engine,
open Codex, access credentials, or read customer data. Install dependencies from
requirements-dev.txt before running; source files are read from this checkout.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import posixpath
import shlex
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import unquote, urlsplit

BEGIN = "<!-- BEGIN MADDY CRM RULES -->"
END = "<!-- END MADDY CRM RULES -->"
BUNDLE = ".crm-rules"
BACKUPS = ".crm-rules-backups"
METADATA = "install-metadata.json"
OWNER = "maddy-crm-static-rules"
PATH_KEYS = {"config", "operating_reference", "workplan_minimums_remain_in_config"}


class InstallError(Exception):
    """A conflicting or unsafe local layout; no automatic reset is attempted."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def relative_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise InstallError(f"Invalid relative path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or PureWindowsPath(value).is_absolute() or any(
        part in {"..", "."} for part in value.split("/")
    ):
        raise InstallError(f"Absolute paths and path traversal are unsupported: {value!r}")
    if any(not part for part in value.split("/")) or ":" in value:
        raise InstallError(f"Invalid relative path: {value!r}")
    return str(path)


def checked_path(root: Path, relative: str, *, file: bool = False) -> Path:
    relative = relative_path(relative)
    path = root
    for part in PurePosixPath(relative).parts:
        path = path / part
        if path.is_symlink():
            raise InstallError(f"Symlink paths are unsupported: {path}")
        if path != root / relative and path.exists() and not path.is_dir():
            raise InstallError(f"Parent path is not a directory: {path}")
    if path.exists() and file and not path.is_file():
        raise InstallError(f"File destination is incompatible: {path}")
    return path


def existing_directory(path: Path, label: str) -> Path:
    absolute = Path(os.path.abspath(path))
    for item in (absolute, *absolute.parents):
        if item.is_symlink():
            raise InstallError(f"{label} uses a symlink: {item}")
    if not absolute.is_dir():
        raise InstallError(f"{label} must be an existing directory: {absolute}")
    return absolute


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise InstallError(f"Cannot read metadata {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise InstallError(f"Metadata must be an object: {path}")
    return value


def source_revision(source: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=False, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def build_bundle(source: Path) -> dict[str, bytes]:
    """Follow active file references; do not recursively copy the repository."""
    validator_path = checked_path(source, "scripts/validate_rules.py", file=True)
    try:
        spec = importlib.util.spec_from_file_location("crm_snapshot_validator", validator_path)
        if spec is None or spec.loader is None:
            raise InstallError("Cannot load the source rule validator")
        validator_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validator_module)
    except ModuleNotFoundError as exc:
        raise InstallError(
            "Install local validation dependencies first: "
            f"{sys.executable} -m pip install -r {source / 'requirements-dev.txt'}"
        ) from exc
    yaml = validator_module.yaml
    parser = validator_module.MarkdownIt("commonmark")
    manifest_path = checked_path(source, "rules.yaml", file=True)
    try:
        manifest = yaml.load(manifest_path.read_text(encoding="utf-8"), Loader=validator_module.UniqueKeyLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise InstallError(f"Cannot read rules.yaml: {exc}") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), dict):
        raise InstallError("rules.yaml must contain the active files mapping")
    excluded = manifest.get("excluded_sources", [])
    if not isinstance(excluded, list) or any(not isinstance(item, str) for item in excluded):
        raise InstallError("rules.yaml excluded_sources must be a list of paths")

    def dependency(href: str, origin: str) -> str | None:
        parsed = urlsplit(href)
        if parsed.scheme or parsed.netloc or not parsed.path:
            return None
        decoded = unquote(parsed.path)
        if not decoded or "\\" in decoded or ":" in decoded or PurePosixPath(decoded).is_absolute() or PureWindowsPath(decoded).is_absolute():
            raise InstallError(f"Invalid local dependency in {origin}: {href!r}")
        # A referenced document may link to ../SKILL.md inside this snapshot.
        # Normalizing against its source directory must never escape the root.
        candidate = posixpath.normpath(str(PurePosixPath(origin).parent / decoded))
        return relative_path(candidate)

    def active_path(relative: str) -> Path:
        relative = relative_path(relative)
        if (
            any(part.lower() in {"archive", "archives", ".git"} for part in PurePosixPath(relative).parts)
            or PurePosixPath(relative).name.startswith("visit-outreach-draft-queue-")
            or any(relative == item.rstrip("/") or relative.startswith(item.rstrip("/") + "/") for item in excluded)
        ):
            raise InstallError(f"Active reference points to excluded historical material: {relative}")
        path = checked_path(source, relative, file=True)
        if not path.is_file():
            raise InstallError(f"Missing active dependency: {relative}")
        return path

    def yaml_refs(value, origin: str):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in PATH_KEYS:
                    if not isinstance(item, str):
                        raise InstallError(f"Invalid file reference in {origin}: {key}")
                    target = dependency(item, origin)
                    if target is None:
                        raise InstallError(f"File reference must be local in {origin}: {item}")
                    pending.append(target)
                yaml_refs(item, origin)
        elif isinstance(value, list):
            for item in value:
                yaml_refs(item, origin)

    pending = ["rules.yaml"]
    pending.extend(relative_path(value) for value in manifest["files"].values())
    files: dict[str, bytes] = {}
    while pending:
        relative = pending.pop()
        if relative in files:
            continue
        path = active_path(relative)
        contents = path.read_bytes()
        files[relative] = contents
        if path.suffix.lower() == ".md":
            text = contents.decode("utf-8")
            for token in parser.parse(text):
                for child in token.children or []:
                    if child.type in {"link_open", "image"}:
                        href = child.attrGet("href" if child.type == "link_open" else "src") or ""
                        target = dependency(href, relative)
                        if target:
                            pending.append(target)
        elif relative == "rules.yaml" or relative in manifest["files"].values() or path.suffix.lower() in {".yaml", ".yml"}:
            try:
                value = yaml.load(contents.decode("utf-8"), Loader=validator_module.UniqueKeyLoader)
            except yaml.YAMLError as exc:
                raise InstallError(f"Cannot parse active file {relative}: {exc}") from exc
            yaml_refs(value, relative)
    for relative in ("scripts/validate_rules.py", "requirements-dev.txt"):
        files[relative] = active_path(relative).read_bytes()
    with tempfile.TemporaryDirectory(prefix="crm-rule-check-") as directory:
        root = Path(directory)
        for relative, contents in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
        validator = validator_module.Validator(root)
        validator.run()
        if validator.errors:
            raise InstallError("Snapshot validation failed:\n" + "\n".join(validator.errors))
    return files


def managed_instructions(original: bytes) -> bytes:
    try:
        text = original.decode("utf-8")
    except UnicodeError as exc:
        raise InstallError("Project instruction file is not UTF-8; no changes made") from exc
    if text.count(BEGIN) != text.count(END) or text.count(BEGIN) > 1:
        raise InstallError("Ambiguous managed instruction markers; repair them before installing")
    newline = "\r\n" if "\r\n" in text else "\n"
    block = "\n".join([
        BEGIN,
        "## Maddy CRM customer-drafting rules",
        "",
        "Read [.crm-rules/rules.yaml](.crm-rules/rules.yaml), then its active files in load_order.",
        "Maddy's current instructions take precedence over repository defaults. For customer",
        "draft preparation, these installed defaults take precedence over older project or",
        "uploaded same-day, cooldown, minimum-length, and mandatory-introduction defaults.",
        "Use .crm-rules/messaging.yaml as the canonical voice and drafting source. Recent",
        "contact, an unanswered question, or missing optional context calls for a different",
        "supported angle or a held draft with review flags, rather than a blanket no-draft",
        "result. Use same-day unattempted selection only when that specific scope is requested.",
        "Answer the customer's latest question first; identify Maddy when needed, keep copy",
        "short, and do not pad it. Use conditional price-to-visit questions without unapproved",
        "price or payment promises. Follow the canonical rules for identity, channel opt-outs,",
        "and truthful evidence-based claims. Keep DRAFT_ONLY: these instructions authorize no",
        "CRM sending, composer saves, task completion, appointment creation, or mutations.",
        "",
        "Use .crm-rules/assistant-coordination.yaml for verified private packets and one active",
        "draft author per customer and channel. Keep each chat's browser access independent;",
        "share no credentials, cookies, tab handles, or browser sessions. Do not invent",
        "current quotas, cooldown durations, inventory facts, customer facts, or live counts.",
        "This is a static local rule installation. An existing drafting engine still needs",
        "its own verified integration, and cross-chat coordination needs an actual private",
        "shared artifact. Do not claim the runtime or five chats were updated or connected.",
        END,
    ]).replace("\n", newline)
    if BEGIN in text:
        start = text.index(BEGIN)
        stop = text.index(END) + len(END)
        if stop <= start or (start and text[start - 1] != "\n") or (stop < len(text) and text[stop] not in "\r\n"):
            raise InstallError("Managed markers must be standalone lines in the correct order")
        return (text[:start] + block + text[stop:]).encode("utf-8")
    separator = "" if not text else newline if text.endswith(("\n", "\r")) else newline + newline
    return (text + separator + block + newline).encode("utf-8")


def install_plan(project: Path, source: Path) -> dict[str, bytes | None]:
    if project == source or project.is_relative_to(source / BUNDLE):
        raise InstallError("Use an existing assistant project separate from this source checkout")
    bundle = checked_path(project, BUNDLE)
    previous = None
    if bundle.exists():
        if not bundle.is_dir():
            raise InstallError(f"{bundle} must be a directory")
        metadata_path = checked_path(project, f"{BUNDLE}/{METADATA}", file=True)
        if not metadata_path.is_file():
            raise InstallError(f"Existing {bundle} is unmanaged; move it aside before installing")
        previous = load_json(metadata_path)
        if previous.get("managed_by") != OWNER or previous.get("format_version") != 1:
            raise InstallError(f"Existing {bundle} has incompatible metadata")
        managed = previous.get("managed_files")
        if not isinstance(managed, list) or any(not isinstance(item, str) for item in managed) or len(managed) != len(set(managed)):
            raise InstallError("Installed managed_files metadata is invalid")
        for relative in managed:
            checked_path(project, f"{BUNDLE}/{relative_path(relative)}", file=True)
    files = build_bundle(source)
    hashes = {name: digest(contents) for name, contents in sorted(files.items())}
    metadata = {
        "format_version": 1,
        "managed_by": OWNER,
        "managed_files": sorted(files),
        "sha256": hashes,
        "source_git_revision": source_revision(source),
        "source_snapshot_sha256": digest(json_bytes(hashes)),
        "runtime_updated": False,
    }
    if previous and all(previous.get(key) == value for key, value in metadata.items()):
        metadata["installed_at_utc"] = previous.get("installed_at_utc")
    else:
        metadata["installed_at_utc"] = datetime.now(timezone.utc).isoformat()
    desired: dict[str, bytes | None] = {f"{BUNDLE}/{name}": content for name, content in files.items()}
    desired[f"{BUNDLE}/{METADATA}"] = json_bytes(metadata)
    if previous:
        for old in previous["managed_files"]:
            if old not in files:
                desired[f"{BUNDLE}/{old}"] = None
    override = checked_path(project, "AGENTS.override.md", file=True)
    instruction_name = "AGENTS.override.md" if override.exists() else "AGENTS.md"
    instruction_path = checked_path(project, instruction_name, file=True)
    original = instruction_path.read_bytes() if instruction_path.exists() else b""
    desired[instruction_name] = managed_instructions(original)
    return changed_plan(project, desired)


def changed_plan(project: Path, desired: dict[str, bytes | None]) -> dict[str, bytes | None]:
    changes = {}
    for relative, content in sorted(desired.items()):
        path = checked_path(project, relative, file=True)
        existing = path.read_bytes() if path.exists() else None
        if existing != content:
            changes[relative] = content
    return changes


def restore_plan(project: Path, backup: Path) -> tuple[dict[str, bytes | None], list[str]]:
    backups_root = checked_path(project, BACKUPS)
    backup = existing_directory(backup, "Backup")
    if backup.parent != backups_root:
        raise InstallError(f"Backup must be a direct child of {backups_root}")
    manifest = load_json(checked_path(backup, "restore.json", file=True))
    if manifest.get("format_version") != 1 or manifest.get("managed_by") != OWNER or manifest.get("project") != str(project):
        raise InstallError("Backup does not belong to this project or installer")
    records = manifest.get("files")
    if not isinstance(records, dict):
        raise InstallError("Backup file records are invalid")
    desired = {}
    for relative, record in records.items():
        relative = relative_path(relative)
        if relative not in {"AGENTS.md", "AGENTS.override.md"} and not relative.startswith(BUNDLE + "/"):
            raise InstallError(f"Backup path outside managed destinations: {relative}")
        if not isinstance(record, dict) or type(record.get("existed")) is not bool:
            raise InstallError(f"Invalid backup record: {relative}")
        current = checked_path(project, relative, file=True)
        current_content = current.read_bytes() if current.exists() else None
        if (digest(current_content) if current_content is not None else None) != record.get("written_sha256"):
            raise InstallError(f"Refusing rollback: {relative} changed after this backup")
        if record["existed"]:
            content = checked_path(backup, f"files/{relative}", file=True).read_bytes()
            if digest(content) != record.get("original_sha256"):
                raise InstallError(f"Backup content checksum mismatch: {relative}")
            desired[relative] = content
        else:
            desired[relative] = None
    directories = manifest.get("created_directories", [])
    if not isinstance(directories, list) or any(not isinstance(item, str) for item in directories):
        raise InstallError("Backup directory records are invalid")
    for relative in directories:
        if relative != BUNDLE and not relative.startswith(BUNDLE + "/"):
            raise InstallError(f"Invalid directory in backup: {relative}")
        checked_path(project, relative)
    return changed_plan(project, desired), directories


def atomic_write(target: Path, content: bytes):
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".crm-write-", dir=target.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
        if target.exists():
            os.chmod(temporary, target.stat().st_mode & 0o777)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def apply_plan(project: Path, changes: dict[str, bytes | None]) -> Path | None:
    if not changes:
        return None
    # Check every destination before persisting backups or writing any project file.
    for relative in changes:
        checked_path(project, relative, file=True)
    backups_root = checked_path(project, BACKUPS)
    if backups_root.exists() and not backups_root.is_dir():
        raise InstallError(f"Backup destination is incompatible: {backups_root}")
    backups_root.mkdir(exist_ok=True)
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ-") + uuid.uuid4().hex[:12]
    backup = backups_root / name
    backup.mkdir()
    records = {}
    created_directories: set[str] = set()
    for relative, content in changes.items():
        target = checked_path(project, relative, file=True)
        existed = target.exists()
        original = target.read_bytes() if existed else None
        if original is not None:
            copy = backup / "files" / relative
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_bytes(original)
        if content is not None:
            for parent in target.parents:
                if parent == project:
                    break
                if not parent.exists():
                    created_directories.add(parent.relative_to(project).as_posix())
        records[relative] = {
            "existed": existed,
            "original_sha256": digest(original) if original is not None else None,
            "written_sha256": digest(content) if content is not None else None,
        }
    (backup / "restore.json").write_bytes(json_bytes({
        "format_version": 1, "managed_by": OWNER, "project": str(project),
        "files": records, "created_directories": sorted(created_directories),
    }))
    written = []
    try:
        for relative, content in changes.items():
            target = checked_path(project, relative, file=True)
            if content is None:
                target.unlink()
            else:
                atomic_write(target, content)
            written.append(relative)
    except OSError as exc:
        failures = []
        for relative in reversed(written):
            try:
                target = checked_path(project, relative, file=True)
                if records[relative]["existed"]:
                    atomic_write(target, (backup / "files" / relative).read_bytes())
                else:
                    target.unlink(missing_ok=True)
            except (OSError, InstallError) as rollback_error:
                failures.append(f"{relative}: {rollback_error}")
        for relative in sorted(created_directories, key=lambda value: len(PurePosixPath(value).parts), reverse=True):
            directory = checked_path(project, relative)
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
        detail = "Original project files restored." if not failures else "Manual recovery needed: " + "; ".join(failures)
        raise InstallError(f"Write failed. {detail} Backup preserved: {backup}. {exc}") from exc

    return backup


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True, help="Existing local assistant project directory")
    parser.add_argument("--apply", action="store_true", help="Apply reviewed changes; default is dry-run")
    parser.add_argument("--restore-backup", type=Path, help="Restore a backup belonging to this project; also defaults to dry-run")
    args = parser.parse_args(argv)
    try:
        project = existing_directory(args.project, "Project")
        source = existing_directory(Path(__file__).resolve().parents[1], "Source checkout")
        cleanup = []
        if args.restore_backup:
            changes, cleanup = restore_plan(project, args.restore_backup)
        else:
            changes = install_plan(project, source)
        print(f"{'APPLY' if args.apply else 'DRY RUN'}: {project}")
        for relative, content in changes.items():
            path = project / relative
            operation = "remove managed file" if content is None else "update" if path.exists() else "create"
            print(f"  {operation}: {relative}")
        if not changes:
            print("Already current; no files changed and no backup created.")
        elif args.apply:
            backup = apply_plan(project, changes)
            for relative in sorted(cleanup, key=lambda value: len(PurePosixPath(value).parts), reverse=True):
                directory = checked_path(project, relative)
                if directory.is_dir() and not any(directory.iterdir()):
                    directory.rmdir()
            print(f"Backup preserved: {backup}")
            print("To reverse these changes (preview without --apply):")
            command = [sys.executable, str(Path(__file__).resolve()), "--project", str(project), "--restore-backup", str(backup), "--apply"]
            print("  " + shlex.join(command))
        else:
            print("No project files written. Rerun with --apply to install this plan.")
        print("Static rule snapshot only; runtime_updated=false. No engine, chats, CRM, or browser changed.")
        if not args.restore_backup:
            print(f"Validate the installed bundle: {sys.executable} {project / BUNDLE / 'scripts/validate_rules.py'}")
        return 0
    except (InstallError, OSError, UnicodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
