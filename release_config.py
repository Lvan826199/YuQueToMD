"""Shared release naming rules derived from the project version."""

import re

from version import __version__


SEMVER_PATTERN = re.compile(r"\d+\.\d+\.\d+")


def release_version() -> str:
    """Return the validated release version from the single version source."""
    if not SEMVER_PATTERN.fullmatch(__version__):
        raise ValueError(f"Invalid release version: {__version__!r}")
    return __version__


def release_artifact_stem() -> str:
    """Return the platform-independent executable stem for a release."""
    return f"MWJDocs-v{release_version()}"


def release_exe_name() -> str:
    """Return the Windows release artifact name."""
    return f"{release_artifact_stem()}.exe"
