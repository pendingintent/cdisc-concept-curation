"""Package a release archive for non-technical end users.

Produces dist/cdisc-concept-curation-<version>.zip and .tar.gz containing
every git-tracked file from this repo AND the cdisc-bc-ncit-alignment
submodule (as plain files, no .git), plus the double-click installer
(install.py, install.sh, "Install (Mac).command", "Install (Windows).bat").

A plain "Download ZIP" or `git archive` of this repo does NOT include
submodule content (submodules are just gitlink pointers) -- this script
exists specifically to avoid shipping a broken archive. Intended to be run
by .github/workflows/release.yml on a git checkout made with
`submodules: recursive`, but also works locally for testing.

Usage:
    python scripts/build_release.py [--version VERSION] [--out-dir DIST_DIR]
"""

import argparse
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_NAME = "cdisc-concept-curation"
EXECUTABLE_SUFFIXES = {".sh", ".command"}


def run(cmd, cwd=REPO_ROOT):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout


def default_version():
    try:
        return subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return f"dev-{date.today().isoformat()}"


def tracked_files():
    """Files tracked by git in this repo AND the submodule, without gitlinks."""
    output = run(["git", "ls-files", "--recurse-submodules"])
    return [line for line in output.splitlines() if line]


def check_submodule_populated(files):
    submodule_files = [f for f in files if f.startswith("cdisc-bc-ncit-alignment/")]
    if not submodule_files:
        sys.exit(
            "cdisc-bc-ncit-alignment/ has no tracked files -- the submodule is not "
            "checked out. Run `git submodule update --init --recursive` (or checkout "
            "with `submodules: recursive` in CI) before packaging a release."
        )


def stage_files(files, staging_root):
    for rel_path in files:
        src = REPO_ROOT / rel_path
        dst = staging_root / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        if dst.suffix in EXECUTABLE_SUFFIXES:
            dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def build_zip(staging_root, out_path):
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(staging_root.rglob("*")):
            if path.is_dir():
                continue
            arcname = path.relative_to(staging_root.parent)
            info = zipfile.ZipInfo.from_file(path, arcname=str(arcname))
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = path.stat().st_mode
            if path.suffix in EXECUTABLE_SUFFIXES:
                mode |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
            info.external_attr = (mode & 0xFFFF) << 16
            info.create_system = 3  # unix, so external_attr is honored on extract
            with open(path, "rb") as f:
                zf.writestr(info, f.read())


def build_tar(staging_root, out_path):
    with tarfile.open(out_path, "w:gz") as tf:
        tf.add(staging_root, arcname=staging_root.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=None, help="Release version, e.g. v1.2.3 (default: git describe)")
    parser.add_argument("--out-dir", default=str(REPO_ROOT / "dist"), help="Output directory (default: ./dist)")
    args = parser.parse_args()

    version = args.version or default_version()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = tracked_files()
    check_submodule_populated(files)

    folder_name = f"{ARCHIVE_NAME}-{version}"
    with tempfile.TemporaryDirectory() as tmp:
        staging_root = Path(tmp) / folder_name
        stage_files(files, staging_root)

        zip_path = out_dir / f"{folder_name}.zip"
        tar_path = out_dir / f"{folder_name}.tar.gz"
        build_zip(staging_root, zip_path)
        build_tar(staging_root, tar_path)

    print(f"Wrote {zip_path} ({zip_path.stat().st_size:,} bytes)")
    print(f"Wrote {tar_path} ({tar_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
