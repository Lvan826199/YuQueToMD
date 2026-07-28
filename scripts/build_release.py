"""Build, verify and publish the current versioned Windows executable."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from release_config import release_exe_name, release_version  # noqa: E402


DIST_DIR = PROJECT_ROOT / "dist"
MANAGED_EXE_PATTERN = re.compile(
    r"MWJDocs(?:-v\d+\.\d+\.\d+)?\.exe",
    re.IGNORECASE,
)


def is_managed_exe_name(name: str) -> bool:
    """Limit cleanup to legacy and SemVer release executables."""
    return MANAGED_EXE_PATTERN.fullmatch(name) is not None


def remove_old_artifacts(directory: Path, expected_name: str) -> list[Path]:
    """Remove managed executables other than the newly verified artifact."""
    removed: list[Path] = []
    if not directory.is_dir():
        return removed

    resolved_directory = directory.resolve()
    for candidate in directory.iterdir():
        if not candidate.is_file():
            continue
        if candidate.name == expected_name or not is_managed_exe_name(candidate.name):
            continue
        if candidate.resolve().parent != resolved_directory:
            raise RuntimeError(f"Refusing to remove artifact outside {directory}: {candidate}")
        candidate.unlink()
        removed.append(candidate)
    return removed


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_version_sources(version: str, artifact_name: str) -> None:
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version_info = (PROJECT_ROOT / "version_info.txt").read_text(encoding="utf-8")
    version_tuple = ", ".join((*version.split("."), "0"))

    expected_markers = {
        "pyproject.toml": f'version = "{version}"',
        "version_info.txt ProductVersion": f'StringStruct("ProductVersion", "{version}")',
        "version_info.txt FileVersion": f'StringStruct("FileVersion", "{version}")',
        "version_info.txt filevers": f"filevers=({version_tuple})",
        "version_info.txt OriginalFilename": (
            f'StringStruct("OriginalFilename", "{artifact_name}")'
        ),
    }
    contents = {
        "pyproject.toml": pyproject,
        "version_info.txt ProductVersion": version_info,
        "version_info.txt FileVersion": version_info,
        "version_info.txt filevers": version_info,
        "version_info.txt OriginalFilename": version_info,
    }
    missing = [label for label, marker in expected_markers.items() if marker not in contents[label]]
    if missing:
        raise RuntimeError("Release version metadata is not synchronized: " + ", ".join(missing))


def run_command(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=True,
        text=True,
        **kwargs,
    )


def validate_executable(artifact: Path, version: str) -> None:
    result = run_command(
        [str(artifact), "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    if not result.stdout.strip().endswith(version):
        raise RuntimeError(
            f"Unexpected --version output from {artifact.name}: {result.stdout.strip()!r}"
        )

    powershell_script = (
        "$info=(Get-Item -LiteralPath $env:MWJDOCS_RELEASE_EXE).VersionInfo; "
        "Write-Output $info.FileVersion; Write-Output $info.ProductVersion"
    )
    command_environment = os.environ.copy()
    command_environment["MWJDOCS_RELEASE_EXE"] = str(artifact)
    metadata = run_command(
        ["powershell", "-NoProfile", "-Command", powershell_script],
        env=command_environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    versions = [line.strip() for line in metadata.stdout.splitlines() if line.strip()]
    if versions != [version, version]:
        raise RuntimeError(
            f"Unexpected Windows version metadata for {artifact.name}: {versions!r}"
        )


def main() -> int:
    if sys.platform != "win32":
        raise RuntimeError("The release EXE must be built on Windows")

    version = release_version()
    artifact_name = release_exe_name()
    validate_version_sources(version, artifact_name)

    run_command(
        [sys.executable, "-m", "PyInstaller", "serve.spec", "--noconfirm"]
    )
    built_artifact = DIST_DIR / artifact_name
    if not built_artifact.is_file():
        raise FileNotFoundError(f"Expected build artifact was not created: {built_artifact}")

    validate_executable(built_artifact, version)

    repository_artifact = PROJECT_ROOT / artifact_name
    temporary_artifact = PROJECT_ROOT / f".{artifact_name}.tmp"
    try:
        shutil.copy2(built_artifact, temporary_artifact)
        temporary_artifact.replace(repository_artifact)
    finally:
        temporary_artifact.unlink(missing_ok=True)

    removed = remove_old_artifacts(PROJECT_ROOT, artifact_name)
    removed.extend(remove_old_artifacts(DIST_DIR, artifact_name))

    checksum = sha256sum(built_artifact)
    checksum_file = DIST_DIR / "SHA256SUMS.txt"
    checksum_file.write_text(f"{checksum}  {artifact_name}\n", encoding="utf-8")

    print(f"Release artifact: {repository_artifact}")
    print(f"SHA-256: {checksum}")
    if removed:
        print("Removed old artifacts:")
        for path in removed:
            print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
