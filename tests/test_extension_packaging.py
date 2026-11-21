"""
Chromium unpacked extension packaging & filesystem hygiene gates.

Enforces Chromium's `extensions::file_util::CheckForIllegalFilenames` contract
on both the repository root (`manifest.json`) and `extension/` (`extension/manifest.json`),
ensuring Python bytecode directories (`__pycache__`) or other reserved leading-underscore
entries can never silently break `chrome://extensions` Load Unpacked or Reload.
"""
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTENSION_DIR = REPO_ROOT / "extension"

# Mirrors Chromium extensions/common/file_util.cc CheckForIllegalFilenames().
# Unpacked extensions only permit _locales and _platform_specific at the root;
# any other "_" prefix (such as __pycache__) causes Chromium to fail manifest load
# and disable the extension with DISABLE_RELOAD.
CHROMIUM_ALLOWED_UNPACKED_UNDERSCORE_ENTRIES = frozenset({
    "_locales",
    "_platform_specific",
})


def find_illegal_unpacked_entries(root: Path) -> list[str]:
    """Return top-level filenames/directories violating Chromium's leading-'_' rule."""
    illegal: list[str] = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        name = entry.name
        if name.startswith("_") and name not in CHROMIUM_ALLOWED_UNPACKED_UNDERSCORE_ENTRIES:
            illegal.append(name)
    return illegal


class TestExtensionPackagingGate(unittest.TestCase):
    def test_repo_root_has_no_chromium_illegal_underscore_entries(self):
        """Repo root serves manifest.json for unpacked browser loads; leading-'_' dirs like __pycache__ break reload."""
        illegal = find_illegal_unpacked_entries(REPO_ROOT)
        self.assertEqual(
            illegal,
            [],
            f"Chromium forbids top-level '_' entries in unpacked extension root {REPO_ROOT}: {illegal}. "
            "Remove them (e.g. `rm -rf __pycache__`) and invoke Python with `-B` / `PYTHONDONTWRITEBYTECODE=1`.",
        )

    def test_extension_subdir_has_no_chromium_illegal_underscore_entries(self):
        """extension/ serves extension/manifest.json for clean unpacked & release loads."""
        illegal = find_illegal_unpacked_entries(EXTENSION_DIR)
        self.assertEqual(
            illegal,
            [],
            f"Chromium forbids top-level '_' entries in {EXTENSION_DIR}: {illegal}.",
        )

    def test_root_and_subdir_manifests_are_valid_and_in_parity(self):
        """Both manifests must parse cleanly, share version/name, and reference only existing assets."""
        root_manifest = json.loads((REPO_ROOT / "manifest.json").read_text(encoding="utf-8"))
        ext_manifest = json.loads((EXTENSION_DIR / "manifest.json").read_text(encoding="utf-8"))

        for key in ("manifest_version", "name", "version", "description", "permissions", "host_permissions"):
            self.assertEqual(
                root_manifest.get(key),
                ext_manifest.get(key),
                f"Manifest drift between manifest.json and extension/manifest.json on key '{key}'",
            )

        for base_dir, manifest in ((REPO_ROOT, root_manifest), (EXTENSION_DIR, ext_manifest)):
            referenced: list[str] = []
            sw = (manifest.get("background") or {}).get("service_worker")
            if sw:
                referenced.append(sw)
            popup = (manifest.get("action") or {}).get("default_popup")
            if popup:
                referenced.append(popup)
            for icon_map in (manifest.get("icons") or {}, (manifest.get("action") or {}).get("default_icon") or {}):
                referenced.extend(icon_map.values())
            for cs in manifest.get("content_scripts") or []:
                referenced.extend(cs.get("js") or [])
                referenced.extend(cs.get("css") or [])

            for rel in referenced:
                target = base_dir / rel
                self.assertTrue(
                    target.is_file(),
                    f"Manifest in {base_dir} references missing asset: {rel}",
                )

    def test_python_entrypoints_suppress_bytecode_writing(self):
        """Daemon and CLI wrappers must suppress bytecode so repo root stays free of __pycache__."""
        cli_py = (REPO_ROOT / "cli.py").read_text(encoding="utf-8")
        self.assertIn("dont_write_bytecode", cli_py)
        self.assertIn("-B", cli_py.splitlines()[0])

        bin_cli = (REPO_ROOT / "bin" / "spark-otp").read_text(encoding="utf-8")
        self.assertIn("-B", bin_cli.splitlines()[0])

        daemon_sh = (REPO_ROOT / "scripts" / "manage_daemon.sh").read_text(encoding="utf-8")
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", daemon_sh)


if __name__ == "__main__":
    unittest.main()
