"""Pytest configuration and driver lifecycle for Android Appium testing."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

import pytest
from appium import webdriver
from appium.options.android import UiAutomator2Options


def _env_bool(var_name: str, default: bool) -> bool:
    val = os.getenv(var_name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def build_driver_options() -> UiAutomator2Options:
    """Build UiAutomator2Options from environment variables with sensible defaults."""
    options = UiAutomator2Options()
    options.platform_name = os.getenv("ANDROID_PLATFORM_NAME", "Android")
    options.automation_name = os.getenv("ANDROID_AUTOMATION_NAME", "UiAutomator2")
    options.device_name = os.getenv("ANDROID_DEVICE_NAME", "emulator-5554")

    platform_version = os.getenv("ANDROID_PLATFORM_VERSION", "14")
    if platform_version:
        options.platform_version = platform_version

    # Application path or package/activity
    default_app_path = Path(__file__).resolve().parent.parent / "apps" / "mda-2.3.0-27.apk"
    fallback_path = str(default_app_path) if default_app_path.is_file() else ""
    app_path = os.getenv("ANDROID_APP_PATH", fallback_path)
    if app_path:
        options.app = app_path

    options.app_package = os.getenv("ANDROID_APP_PACKAGE", "com.saucelabs.mydemoapp.android")
    options.app_activity = os.getenv(
        "ANDROID_APP_ACTIVITY",
        "com.saucelabs.mydemoapp.android.view.activities.SplashActivity",
    )
    options.app_wait_activity = os.getenv(
        "ANDROID_APP_WAIT_ACTIVITY",
        "com.saucelabs.mydemoapp.android.view.activities.MainActivity,com.saucelabs.mydemoapp.android.view.activities.SplashActivity",
    )

    options.no_reset = _env_bool("ANDROID_NO_RESET", False)
    options.full_reset = _env_bool("ANDROID_FULL_RESET", False)
    options.auto_grant_permissions = _env_bool("ANDROID_AUTO_GRANT_PERMISSIONS", True)

    # Performance and stability flags
    options.new_command_timeout = int(os.getenv("APPIUM_NEW_COMMAND_TIMEOUT", "120"))
    options.uiautomator2_server_install_timeout = int(
        os.getenv("UIAUTOMATOR2_SERVER_INSTALL_TIMEOUT", "60000")
    )
    options.uiautomator2_server_launch_timeout = int(
        os.getenv("UIAUTOMATOR2_SERVER_LAUNCH_TIMEOUT", "60000")
    )

    return options


@pytest.fixture(scope="function")
def driver() -> Generator[webdriver.WebDriver, None, None]:
    """Provide an isolated Appium UiAutomator2 WebDriver instance per test."""
    appium_url = os.getenv("APPIUM_SERVER_URL", "http://127.0.0.1:4723")
    options = build_driver_options()

    appium_driver = webdriver.Remote(appium_url, options=options)
    appium_driver.implicitly_wait(0)  # Zero implicit wait; explicit WebDriverWait only

    try:
        yield appium_driver
    finally:
        try:
            appium_driver.quit()
        except Exception:
            pass


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """Save screenshot, page source XML, and logcat to artifacts/ on test failure."""
    outcome = yield
    report: pytest.TestReport = outcome.get_result()

    if report.when == "call" and report.failed:
        test_driver = item.funcargs.get("driver") if hasattr(item, "funcargs") else None
        if test_driver is not None:
            artifacts_dir = Path("artifacts")
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            sanitized_name = report.nodeid.replace("/", "_").replace("\\", "_").replace("::", "_")

            # 1. Screenshot (.png)
            screenshot_path = artifacts_dir / f"{sanitized_name}.png"
            try:
                test_driver.save_screenshot(str(screenshot_path))
            except Exception as e:
                print(f"[conftest] Failed to capture screenshot: {e}")

            # 2. Page source (.xml)
            source_path = artifacts_dir / f"{sanitized_name}_page_source.xml"
            try:
                page_source = test_driver.page_source
                source_path.write_text(page_source, encoding="utf-8")
            except Exception as e:
                print(f"[conftest] Failed to capture page source: {e}")

            # 3. Logcat (.log)
            logcat_path = artifacts_dir / f"{sanitized_name}_logcat.log"
            try:
                entries = test_driver.get_log("logcat")
                formatted = [
                    f"[{entry.get('timestamp')}] {entry.get('level')}: {entry.get('message')}"
                    for entry in entries
                ]
                logcat_path.write_text("\n".join(formatted), encoding="utf-8")
            except Exception as e:
                print(f"[conftest] Failed to capture logcat: {e}")
