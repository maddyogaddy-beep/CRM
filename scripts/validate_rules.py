#!/usr/bin/env python3
"""Validate the active CRM rule files without connecting to a CRM or browser.

This checks file loading, references, and explicit configuration contracts. It
does not execute an assistant or establish that a separate chat loads these rules.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml
from markdown_it import MarkdownIt


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject duplicate mapping keys instead of silently accepting the last one."""


def unique_mapping(loader: UniqueKeyLoader, node: yaml.MappingNode, deep=False):
    loader.flatten_mapping(node)
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in result
        except TypeError as exc:
            raise yaml.constructor.ConstructorError(
                None, None, "mapping key must be hashable", key_node.start_mark
            ) from exc
        if duplicate:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key {key!r}", key_node.start_mark
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping
)

FILE_ROLES = {
    "skill",
    "messaging",
    "lead_source_playbooks",
    "conversion_goals",
    "daily_workplan",
    "assistant_coordination",
}
PATH_KEYS = {"config", "workplan_minimums_remain_in_config", "operating_reference"}
ACTION_MODE_KEYS = {"action_mode", "default_action_mode"}


class Missing:
    def __repr__(self):
        return "<missing>"


MISSING = Missing()


class Validator:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.errors: list[str] = []
        self.checked_paths: set[Path] = set()
        self.documents: set[Path] = set()

    def error(self, message: str):
        self.errors.append(message)

    def label(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)

    def resolve(self, value, source: Path, context: str) -> Path | None:
        if not isinstance(value, str) or not value.strip():
            self.error(f"{context}: expected a nonempty relative file path")
            return None
        try:
            parsed = urlsplit(value)
        except ValueError as exc:
            self.error(f"{context}: invalid file path {value!r}: {exc}")
            return None
        if parsed.scheme or parsed.netloc or Path(parsed.path).is_absolute():
            self.error(f"{context}: expected a local relative path, got {value!r}")
            return None
        path = (source.parent / unquote(parsed.path)).resolve()
        if not path.is_relative_to(self.root):
            self.error(f"{context}: path leaves the repository: {value!r}")
            return None
        if not path.is_file():
            self.error(f"{context}: missing file {self.label(path)}")
            return None
        self.checked_paths.add(path)
        if path.suffix.lower() == ".md":
            self.documents.add(path)
        return path

    def yaml_mapping(self, path: Path, text: str | None = None) -> dict | None:
        try:
            contents = path.read_text(encoding="utf-8") if text is None else text
            value = yaml.load(contents, Loader=UniqueKeyLoader)
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            self.error(f"{self.label(path)}: cannot load YAML: {exc}")
            return None
        if not isinstance(value, dict):
            self.error(f"{self.label(path)}: YAML root must be a mapping")
            return None
        return value

    def field(self, data: dict, dotted: str):
        value = data
        for part in dotted.split("."):
            if not isinstance(value, dict) or part not in value:
                return MISSING
            value = value[part]
        return value

    def require(self, data: dict, dotted: str, expected, source: Path):
        value = self.field(data, dotted)
        # bool subclasses int in Python: use exact types for policy numbers.
        if type(value) is not type(expected) or value != expected:
            self.error(
                f"{self.label(source)}:{dotted}: expected {expected!r} "
                f"({type(expected).__name__}), got {value!r}"
            )

    def integer(self, data: dict, dotted: str, source: Path, minimum: int = 0):
        value = self.field(data, dotted)
        if type(value) is not int or value < minimum:
            self.error(
                f"{self.label(source)}:{dotted}: expected an integer >= {minimum}, "
                f"got {value!r}"
            )

    def inspect_configuration(self, value, source: Path, prefix=""):
        if isinstance(value, list):
            for index, item in enumerate(value):
                self.inspect_configuration(item, source, f"{prefix}[{index}]")
        elif isinstance(value, dict):
            for key, item in value.items():
                context = f"{prefix}.{key}" if prefix else str(key)
                if key in ACTION_MODE_KEYS:
                    if item != "DRAFT_ONLY" or not isinstance(item, str):
                        self.error(f"{self.label(source)}:{context}: must be DRAFT_ONLY")
                if key in PATH_KEYS:
                    self.resolve(item, source, f"{self.label(source)}:{context}")
                self.inspect_configuration(item, source, context)

    def skill_frontmatter(self, source: Path):
        try:
            text = source.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            self.error(f"{self.label(source)}: cannot read skill: {exc}")
            return
        lines = text.splitlines()
        if not lines or lines[0] != "---" or "---" not in lines[1:]:
            self.error(f"{self.label(source)}: missing YAML frontmatter delimiters")
            return
        end = lines.index("---", 1)
        metadata = self.yaml_mapping(source, "\n".join(lines[1:end]))
        if metadata is None:
            return
        for key in ("name", "description"):
            value = metadata.get(key)
            if not isinstance(value, str) or not value.strip():
                self.error(f"{self.label(source)}: frontmatter {key} must be nonempty text")

    def markdown_links(self):
        parser = MarkdownIt("commonmark")
        for document in sorted(self.documents):
            try:
                tokens = parser.parse(document.read_text(encoding="utf-8"))
            except (OSError, UnicodeError) as exc:
                self.error(f"{self.label(document)}: cannot read Markdown: {exc}")
                continue
            for token in tokens:
                for child in token.children or []:
                    if child.type != "link_open":
                        continue
                    href = child.attrGet("href") or ""
                    try:
                        parsed = urlsplit(href)
                    except ValueError as exc:
                        self.error(f"{self.label(document)}: invalid link {href!r}: {exc}")
                        continue
                    if parsed.scheme or parsed.netloc or not parsed.path:
                        continue
                    self.resolve(href, document, f"{self.label(document)}: link {href!r}")

    def run(self):
        manifest_path = self.root / "rules.yaml"
        manifest = self.yaml_mapping(manifest_path)
        if manifest is None:
            return
        self.require(manifest, "schema_version", 1, manifest_path)
        self.require(manifest, "action_mode", "DRAFT_ONLY", manifest_path)
        entries = manifest.get("files")
        if not isinstance(entries, dict):
            self.error("rules.yaml:files: expected a mapping of active file roles")
            return
        missing_roles = FILE_ROLES - set(entries)
        if missing_roles:
            self.error(f"rules.yaml:files: missing roles {', '.join(sorted(missing_roles))}")
        unexpected_roles = set(entries) - FILE_ROLES
        if unexpected_roles:
            self.error(f"rules.yaml:files: unexpected roles {unexpected_roles!r}")
        load_order = manifest.get("load_order")
        if (
            not isinstance(load_order, list)
            or any(not isinstance(role, str) for role in load_order)
            or len(load_order) != len(FILE_ROLES)
            or set(load_order) != FILE_ROLES
        ):
            self.error("rules.yaml:load_order: must list each active file role exactly once")
        paths: dict[str, Path] = {}
        configs: dict[str, dict] = {}
        for role, value in entries.items():
            source = self.resolve(value, manifest_path, f"rules.yaml:files.{role}")
            if source is None:
                continue
            paths[role] = source
            if role == "skill":
                self.skill_frontmatter(source)
                continue
            data = self.yaml_mapping(source)
            if data is not None:
                configs[role] = data
                self.require(data, "schema_version", 1, source)
                self.inspect_configuration(data, source)
        self.inspect_configuration(manifest, manifest_path)

        messaging = configs.get("messaging")
        if messaging is not None:
            source = paths["messaging"]
            playbook_path = self.field(messaging, "precision_lead_intelligence.source_discipline.config")
            self.require(
                messaging, "precision_lead_intelligence.source_discipline.config",
                entries.get("lead_source_playbooks"), source,
            )
            if playbook_path is MISSING:
                self.error(f"{self.label(source)}: lead-source configuration reference is missing")
            for channel, floor in (("sms", "preferred_min_characters"), ("email", "preferred_min_words")):
                self.require(messaging, f"{channel}.{floor}", 0, source)
                self.require(messaging, f"{channel}.pad_to_minimum_length", False, source)
            self.require(messaging, "drafting.action_mode", "DRAFT_ONLY", source)
            self.require(
                messaging, "drafting.same_day_selection.scope",
                "explicit_unattempted_today_requests_only", source,
            )
            self.require(messaging, "drafting.same_day_selection.apply_as_general_draft_block", False, source)
            self.require(messaging, "drafting.same_day_selection.fresh_inbound_is_reply_handling", True, source)
            for key in (
                "sms.preferred_sentence_count", "sms.preferred_max_characters",
                "sms.absolute_max_characters", "sms.primary_question_limit",
                "email.preferred_max_words", "email.primary_question_limit",
            ):
                self.integer(messaging, key, source, minimum=1)

        goals = configs.get("conversion_goals")
        if goals is not None:
            source = paths["conversion_goals"]
            self.require(goals, "daily_operating_note.workplan_minimums_remain_in_config", entries.get("daily_workplan"), source)
            self.require(goals, "usage.historical_only", True, source)
            self.require(goals, "usage.apply_to_current_month_automatically", False, source)
            self.require(goals, "usage.current_month_goal", None, source)

        workplan = configs.get("daily_workplan")
        if workplan is not None:
            source = paths["daily_workplan"]
            self.require(workplan, "action_mode", "DRAFT_ONLY", source)
            self.require(workplan, "counting.assistant_executed_activity", 0, source)
            for channel in ("calls", "emails", "sms", "appointments"):
                self.integer(workplan, f"requirements.{channel}.minimum", source)

        playbooks = configs.get("lead_source_playbooks")
        if playbooks is not None:
            source = paths["lead_source_playbooks"]
            default = self.field(playbooks, "policy.default_playbook")
            available = playbooks.get("playbooks")
            if not isinstance(default, str) or not isinstance(available, dict) or default not in available:
                self.error(f"{self.label(source)}: default playbook must resolve to a configured playbook")

        coordination = configs.get("assistant_coordination")
        if coordination is not None:
            source = paths["assistant_coordination"]
            self.require(coordination, "action_mode", "DRAFT_ONLY", source)
            self.integer(coordination, "assistant_slots", source, minimum=1)
            self.require(coordination, "access.share_browser_access", False, source)
            self.require(coordination, "access.share_credentials_cookies_tabs_or_session_handles", False, source)
            self.require(coordination, "handoffs.live_customer_data_in_public_repository", False, source)

        for document in self.root.rglob("*.md"):
            relative = document.relative_to(self.root)
            if any(part in {".git", "archive", "archives", "node_modules"} for part in relative.parts):
                continue
            if document.name.startswith("visit-outreach-draft-queue-"):
                continue
            self.documents.add(document)
        self.markdown_links()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    validator = Validator(args.root)
    validator.run()
    if validator.errors:
        for message in validator.errors:
            print(f"ERROR: {message}", file=sys.stderr)
        print(f"FAILED: {len(validator.errors)} static rule validation error(s).", file=sys.stderr)
        return 1
    print(
        f"OK: active rules load consistently; {len(validator.checked_paths)} local files "
        f"and {len(validator.documents)} active Markdown documents checked."
    )
    print("Static validation only; no CRM, browser, or separate assistant was executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
