"""Exercise reversible snapshot installation in isolated synthetic projects."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("install_mac_rules", ROOT / "scripts/install_mac_rules.py")
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = installer.build_bundle(ROOT)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="crm-installer-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.project = self.root / "project"
        self.source.mkdir()
        self.project.mkdir()
        for relative, content in self.fixture.items():
            destination = self.source / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        self.original_agents = b"# Existing project\n\nKeep the local engine configuration.\n"
        (self.project / "AGENTS.md").write_bytes(self.original_agents)
        (self.project / "engine.json").write_bytes(b'{"existing": true}\n')

    def install(self):
        changes = installer.install_plan(self.project, self.source)
        return installer.apply_plan(self.project, changes)

    def assert_no_install(self):
        self.assertEqual((self.project / "AGENTS.md").read_bytes(), self.original_agents)
        self.assertFalse((self.project / installer.BUNDLE).exists())
        self.assertFalse((self.project / installer.BACKUPS).exists())

    def test_default_cli_dry_run_preserves_project(self):
        before = {file.relative_to(self.project): file.read_bytes() for file in self.project.rglob("*") if file.is_file()}
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(installer.main(["--project", str(self.project)]), 0)
        after = {file.relative_to(self.project): file.read_bytes() for file in self.project.rglob("*") if file.is_file()}
        self.assertEqual(before, after)
        self.assert_no_install()
        self.assertIn("DRY RUN", output.getvalue())
        self.assertIn("runtime_updated=false", output.getvalue())

    def test_apply_exact_active_bundle_preserves_unrelated_files(self):
        (self.source / "archive").mkdir()
        (self.source / "archive/customer.txt").write_text("never install")
        (self.source / "visit-outreach-draft-queue-2026-08-12.md").write_text("historical customers")
        (self.source / "unrelated.md").write_text("not a manifest dependency")
        self.install()
        root = self.project / installer.BUNDLE
        installed = {file.relative_to(root).as_posix() for file in root.rglob("*") if file.is_file()}
        self.assertEqual(installed, set(self.fixture) | {installer.METADATA})
        for name, contents in self.fixture.items():
            self.assertEqual((root / name).read_bytes(), contents)
        agents = (self.project / "AGENTS.md").read_bytes()
        self.assertTrue(agents.startswith(self.original_agents))
        self.assertEqual(agents.count(installer.BEGIN.encode()), 1)
        self.assertIn(b"older project or", agents)
        self.assertIn(b"same-day, cooldown, minimum-length, and mandatory-introduction defaults", agents)
        self.assertEqual((self.project / "engine.json").read_bytes(), b'{"existing": true}\n')
        self.assertFalse((self.project / "AGENTS.override.md").exists())
        metadata = json.loads((root / installer.METADATA).read_text())
        self.assertFalse(metadata["runtime_updated"])
        self.assertIsNone(metadata["source_git_revision"])
        self.assertEqual(metadata["managed_files"], sorted(self.fixture))

    def test_second_install_is_idempotent_without_new_backup(self):
        backup = self.install()
        first_bytes = (self.project / "AGENTS.md").read_bytes()
        self.assertEqual(installer.install_plan(self.project, self.source), {})
        self.assertIsNone(self.install())
        self.assertEqual((self.project / "AGENTS.md").read_bytes(), first_bytes)
        self.assertEqual(list((self.project / installer.BACKUPS).iterdir()), [backup])

    def test_existing_override_wins_and_preserves_all_unmanaged_text(self):
        override = self.project / "AGENTS.override.md"
        original = b"# Private local override\r\n\r\nKeep independent browser access.\r\n"
        override.write_bytes(original)
        self.install()
        self.assertTrue(override.read_bytes().startswith(original))
        self.assertEqual((self.project / "AGENTS.md").read_bytes(), self.original_agents)
        self.assertIn(b"\r\n<!-- BEGIN MADDY CRM RULES -->\r\n", override.read_bytes())
        self.assertEqual(installer.install_plan(self.project, self.source), {})

    def test_update_backs_up_exact_bytes_and_retains_unmanaged_bundle_file(self):
        first_backup = self.install()
        notes = self.project / installer.BUNDLE / "local-notes.txt"
        notes.write_bytes(b"Keep this private unrelated note.\n")
        prior = (self.project / installer.BUNDLE / "messaging.yaml").read_bytes()
        with (self.source / "messaging.yaml").open("ab") as handle:
            handle.write(b"\n# New canonical revision for this test.\n")
        second_backup = self.install()
        self.assertNotEqual(first_backup, second_backup)
        self.assertEqual((second_backup / "files/.crm-rules/messaging.yaml").read_bytes(), prior)
        self.assertEqual(notes.read_bytes(), b"Keep this private unrelated note.\n")
        changes, _ = installer.restore_plan(self.project, second_backup)
        reverse_backup = installer.apply_plan(self.project, changes)
        self.assertNotEqual(reverse_backup, second_backup)
        self.assertEqual((self.project / installer.BUNDLE / "messaging.yaml").read_bytes(), prior)
        self.assertEqual(notes.read_bytes(), b"Keep this private unrelated note.\n")

    def test_cli_rollback_restores_original_and_removes_only_created_paths(self):
        backup = self.install()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(installer.main([
                "--project", str(self.project), "--restore-backup", str(backup), "--apply",
            ]), 0)
        self.assertEqual((self.project / "AGENTS.md").read_bytes(), self.original_agents)
        self.assertFalse((self.project / installer.BUNDLE).exists())
        self.assertEqual((self.project / "engine.json").read_bytes(), b'{"existing": true}\n')
        self.assertTrue(backup.exists())
        self.assertIn("Backup preserved", output.getvalue())

    def test_rollback_rejects_changes_made_after_installation(self):
        backup = self.install()
        agents = self.project / "AGENTS.md"
        agents.write_bytes(agents.read_bytes() + b"\nNew user instruction.\n")
        with self.assertRaisesRegex(installer.InstallError, "changed after this backup"):
            installer.restore_plan(self.project, backup)
        self.assertIn(b"New user instruction", agents.read_bytes())

    def test_failed_validation_and_missing_dependency_do_not_mutate(self):
        (self.source / "references/daily-workplan-operating-system.md").unlink()
        with self.assertRaisesRegex(installer.InstallError, "Missing active dependency"):
            self.install()
        self.assert_no_install()
        (self.source / "references/daily-workplan-operating-system.md").write_bytes(
            self.fixture["references/daily-workplan-operating-system.md"]
        )
        path = self.source / "assistant-coordination.yaml"
        path.write_text(path.read_text().replace('action_mode: "DRAFT_ONLY"', 'action_mode: "SEND"'))
        with self.assertRaisesRegex(installer.InstallError, "Snapshot validation failed"):
            self.install()
        self.assert_no_install()

    def test_nested_parent_link_stays_inside_snapshot_and_root_escape_is_rejected(self):
        document = self.source / "references/daily-workplan-operating-system.md"
        with document.open("a", encoding="utf-8") as handle:
            handle.write("\n[Canonical skill](../SKILL.md)\n")
        bundle = installer.build_bundle(self.source)
        self.assertIn("SKILL.md", bundle)
        self.assertIn(b"[Canonical skill](../SKILL.md)", bundle["references/daily-workplan-operating-system.md"])
        with document.open("a", encoding="utf-8") as handle:
            handle.write("\n[Escapes source](../../outside.md)\n")
        with self.assertRaisesRegex(installer.InstallError, "path traversal"):
            self.install()
        self.assert_no_install()

    def test_traversal_and_absolute_manifest_paths_are_rejected(self):
        manifest = self.source / "rules.yaml"
        original = manifest.read_text()
        for reference in ("../outside.yaml", "/tmp/outside.yaml", "C:\\outside.yaml"):
            with self.subTest(reference=reference):
                manifest.write_text(original.replace('"messaging.yaml"', json.dumps(reference)))
                with self.assertRaises(installer.InstallError):
                    self.install()
                self.assert_no_install()

    def test_symlinked_destinations_are_rejected(self):
        external = self.root / "external"
        external.mkdir()
        for relative, target in ((installer.BUNDLE, external), ("AGENTS.override.md", self.project / "AGENTS.md")):
            with self.subTest(relative=relative):
                link = self.project / relative
                link.symlink_to(target)
                with self.assertRaisesRegex(installer.InstallError, "Symlink"):
                    self.install()
                link.unlink()
                self.assert_no_install()
        self.install()
        path = self.project / installer.BUNDLE / "messaging.yaml"
        original = path.read_bytes()
        path.unlink()
        path.symlink_to(self.source / "messaging.yaml")
        with self.assertRaisesRegex(installer.InstallError, "Symlink"):
            self.install()
        self.assertEqual((self.source / "messaging.yaml").read_bytes(), original)

    def test_source_symlink_is_rejected(self):
        skill = self.source / "SKILL.md"
        skill.unlink()
        skill.symlink_to(ROOT / "SKILL.md")
        with self.assertRaisesRegex(installer.InstallError, "Symlink"):
            self.install()
        self.assert_no_install()

    def test_incompatible_unmanaged_bundle_and_ambiguous_markers_are_rejected(self):
        bundle = self.project / installer.BUNDLE
        bundle.mkdir()
        (bundle / "local.txt").write_bytes(b"Unmanaged content")
        with self.assertRaisesRegex(installer.InstallError, "unmanaged"):
            self.install()
        self.assertEqual((bundle / "local.txt").read_bytes(), b"Unmanaged content")
        shutil.rmtree(bundle)
        for text in (
            installer.BEGIN,
            installer.END + "\n" + installer.BEGIN,
            installer.BEGIN + "\n" + installer.END + "\n" + installer.BEGIN + "\n" + installer.END,
            "prefix " + installer.BEGIN + "\n" + installer.END,
        ):
            with self.subTest(text=text):
                (self.project / "AGENTS.md").write_text(text)
                with self.assertRaisesRegex(installer.InstallError, "marker"):
                    self.install()
                self.assertEqual((self.project / "AGENTS.md").read_text(), text)
                self.assertFalse(bundle.exists())

    def test_invalid_project_and_source_project_rejected(self):
        with self.assertRaisesRegex(installer.InstallError, "existing directory"):
            installer.existing_directory(self.root / "missing", "Project")
        with self.assertRaisesRegex(installer.InstallError, "separate"):
            installer.install_plan(self.source, self.source)
        link = self.root / "project-link"
        link.symlink_to(self.project)
        with self.assertRaisesRegex(installer.InstallError, "symlink"):
            installer.existing_directory(link, "Project")

    def test_write_failure_automatically_restores_prior_project(self):
        changes = installer.install_plan(self.project, self.source)
        original_atomic_write = installer.atomic_write
        calls = 0

        def fail_once(target, content):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated disk failure")
            return original_atomic_write(target, content)

        with mock.patch.object(installer, "atomic_write", side_effect=fail_once):
            with self.assertRaisesRegex(installer.InstallError, "Original project files restored"):
                installer.apply_plan(self.project, changes)
        self.assertEqual((self.project / "AGENTS.md").read_bytes(), self.original_agents)
        self.assertFalse((self.project / installer.BUNDLE).exists())
        backups = list((self.project / installer.BACKUPS).iterdir())
        self.assertEqual(len(backups), 1)
        self.assertTrue((backups[0] / "restore.json").is_file())


if __name__ == "__main__":
    unittest.main()
