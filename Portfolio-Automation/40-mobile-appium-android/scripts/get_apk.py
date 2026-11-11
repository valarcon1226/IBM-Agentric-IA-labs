#!/usr/bin/env python3
"""Download and verify Sauce Labs My Demo App Android APK from GitHub releases.

Standard library only. Checks SHA-256 against a fixed known digest.
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

APP_VERSION: str = "2.3.0"
APK_FILENAME: str = "mda-2.3.0-27.apk"
APK_DOWNLOAD_URL: str = (
    f"https://github.com/saucelabs/my-demo-app-android/releases/download/{APP_VERSION}/{APK_FILENAME}"
)
EXPECTED_SHA256: str = "bd3a3d6f2d50e076b2701ed2cc6a0ca82157b40a7033cf5be9f5d084b6591ec8"


def compute_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def download_apk(dest_dir: Path | None = None) -> Path:
    base_dir = dest_dir if dest_dir is not None else Path(__file__).resolve().parent.parent / "apps"
    base_dir.mkdir(parents=True, exist_ok=True)
    target_apk = base_dir / APK_FILENAME

    if target_apk.is_file():
        actual_sha = compute_sha256(target_apk)
        if actual_sha == EXPECTED_SHA256:
            print(f"[OK] APK already present and verified: {target_apk}")
            print(f"     SHA-256: {actual_sha}")
            return target_apk
        print(f"[WARN] Existing APK hash mismatch ({actual_sha}). Re-downloading...")
        target_apk.unlink()

    print(f"Downloading {APK_DOWNLOAD_URL} -> {target_apk}...")
    request = urllib.request.Request(
        APK_DOWNLOAD_URL,
        headers={"User-Agent": "SauceDemo-Appium-Runner/1.0"},
    )
    with urllib.request.urlopen(request) as response, target_apk.open("wb") as out_file:
        while chunk := response.read(65536):
            out_file.write(chunk)

    actual_sha = compute_sha256(target_apk)
    if actual_sha != EXPECTED_SHA256:
        target_apk.unlink(missing_ok=True)
        sys.stderr.write(
            f"[ERROR] SHA-256 verification failed!\n"
            f"  Expected: {EXPECTED_SHA256}\n"
            f"  Actual:   {actual_sha}\n"
        )
        sys.exit(1)

    print(f"[SUCCESS] Download completed and verified: {target_apk}")
    print(f"          SHA-256: {actual_sha}")
    print(f"          Size:    {target_apk.stat().st_size} bytes")
    return target_apk


if __name__ == "__main__":
    download_apk()
