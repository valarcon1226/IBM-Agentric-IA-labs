# Android Mobile Automation Framework (Appium 3 + Python)

> Automated mobile testing framework built with **Appium 3**, **Python**, and **pytest** targeting the open-source **Sauce Labs My Demo App** on Android.

[![Appium](https://img.shields.io/badge/Appium-3.9.0-E10098?logo=appium)](https://appium.io/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python)](https://www.python.org/)
[![pytest](https://img.shields.io/badge/pytest-9.2.0-0A9EDC?logo=pytest)](https://pytest.org/)
[![Driver](https://img.shields.io/badge/Driver-UiAutomator2_8.7.3-3DDC84?logo=android)](https://github.com/appium/appium-uiautomator2-driver)
[![Target](https://img.shields.io/badge/Android-API_34_(Android_14)-3DDC84?logo=android)](https://developer.android.com/about/versions/14)

---

## 1. What Exists Today

This project provides an automated quality engineering framework for Android applications using modern Appium 3 and standard pytest tooling.

Key highlights:

- **Strict Screen Object Model (SOM):** Decoupled UI interactions under `screens/` encapsulating explicit synchronization without brittle ad-hoc calls.
- **Real Layout Locators:** All element locators are derived directly from the application's XML layouts and Java sources (documented in [`docs/LOCATORS.md`](docs/LOCATORS.md)). Positional XPath and coordinate-based clicks are strictly avoided.
- **Zero Sleep Policy:** No static pauses (`time.sleep`). Synchronization relies exclusively on `WebDriverWait` with expected conditions (`visibility_of_element_located`, `element_to_be_clickable`, etc.).
- **Deterministic APK Lifecycle:** Standard-library script (`scripts/get_apk.py`) fetches a pinned release asset (v2.3.0) and validates its cryptographic SHA-256 digest before execution.
- **Automated Failure Forensics:** Custom pytest hook in `tests/conftest.py` captures a viewport screenshot (`.png`), accessibility tree page source (`.xml`), and device `logcat` (`.log`) into `artifacts/` whenever a test fails.
- **Headless CI Emulator Support:** Complete GitHub Actions pipeline executing against an Android 14 (API 34) x86_64 emulator with KVM acceleration.

---

## 2. Test Coverage: Designed vs. Automated

| Scenario # | Test Identifier | Module | Description | Verification Type |
|---|---|---|---|---|
| 1 | `test_catalog_visible_on_open` | `tests/test_catalog.py` | Catalog screen renders on app launch | UI State & Title Assertion |
| 2 | `test_sort_catalog_by_price` | `tests/test_catalog.py` | Sort products by price ascending | Sorting & Numeric Monotonicity |
| 3 | `test_open_product_detail` | `tests/test_catalog.py` | Tap product card and verify detail view | UI Navigation & Information Check |
| 4 | `test_add_to_cart_and_verify_counter` | `tests/test_cart.py` | Add item to cart and assert counter badge updates | Stateful Counter Assertion |
| 5 | `test_remove_from_cart` | `tests/test_cart.py` | Remove item and verify cart empty state | Cart Lifecycle & Clean State |
| 6 | `test_valid_login` | `tests/test_auth.py` | Authenticate with valid demo credentials | Session State & Drawer Toggle |
| 7 | `test_locked_out_user_error` | `tests/test_auth.py` | Attempt login with locked-out account | Error Toast / Message Validation |

---

## 3. Architecture Overview

```mermaid
flowchart TD
    subgraph SUT["System Under Test (Android Device / Emulator)"]
        App["Sauce Labs My Demo App (v2.3.0 APK)"]
        Server["UiAutomator2 Server (io.appium.uiautomator2.server)"]
        Server --> App
    end

    subgraph Host["Appium Server (Node.js)"]
        Appium["Appium 3 Server (:4723)"]
        Driver["appium-uiautomator2-driver (8.7.3)"]
        Appium --> Driver
        Driver <-->|ADB / Net| Server
    end

    subgraph Framework["Test Automation Framework (Python 3.12 + pytest)"]
        Config["conftest.py (UiAutomator2Options + Failure Hooks)"]
        SOM["Screen Objects (screens/)"]
        Tests["Test Specs (tests/)"]

        Config --> SOM
        SOM --> Tests
        Tests -->|Appium-Python-Client 6.x| Appium
    end

    subgraph Forensics["Diagnostics on Failure (artifacts/)"]
        Shot["Screenshot (.png)"]
        Source["Page Source (.xml)"]
        Logs["Device Logcat (.log)"]
        Config -.->|on failure| Forensics
    end
```

---

## 4. Prerequisites & Environment Variables

### Prerequisites

- **Python:** 3.10 or higher (recommended: 3.12 managed via `uv`)
- **Node.js:** v20.x or higher
- **Appium 3:** `npm install -g appium@3.9.0`
- **UiAutomator2 Driver:** `appium driver install uiautomator2@8.7.3`
- **Android SDK:** `platform-tools` (adb), `emulator`, and system image for Android 14 (API 34)

### Environment Variables

| Variable | Default Value | Description |
|---|---|---|
| `APPIUM_SERVER_URL` | `http://127.0.0.1:4723` | URL of the running Appium 3 HTTP server |
| `ANDROID_DEVICE_NAME` | `emulator-5554` | Target Android device ID or emulator serial |
| `ANDROID_PLATFORM_VERSION` | `14` | Android OS version |
| `ANDROID_APP_PATH` | `<project>/apps/mda-2.3.0-27.apk` | Absolute or relative path to the SUT APK |
| `ANDROID_APP_PACKAGE` | `com.saucelabs.mydemoapp.android` | Target Android package name |
| `ANDROID_APP_ACTIVITY` | `...SplashActivity` | Main entry point activity |
| `ANDROID_APP_WAIT_ACTIVITY` | `...MainActivity,...SplashActivity` | Comma-separated list of activities to wait for |
| `ANDROID_NO_RESET` | `false` | Whether to preserve application state between sessions |
| `ANDROID_FULL_RESET` | `false` | Completely uninstall app and clean cache |
| `ANDROID_AUTO_GRANT_PERMISSIONS` | `true` | Automatically accept Android runtime permissions |

---

## 5. Local Setup & Execution Guide

### 1. Set Up Python Environment

Using `uv`:

```bash
uv venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

uv pip install -r requirements.txt -r requirements-dev.txt
```

### 2. Download and Verify Android APK

Run the verification script to retrieve the fixed v2.3.0 release binary:

```bash
python scripts/get_apk.py
```

Expected output:
```
[SUCCESS] Download completed and verified: .../apps/mda-2.3.0-27.apk
          SHA-256: bd3a3d6f2d50e076b2701ed2cc6a0ca82157b40a7033cf5be9f5d084b6591ec8
          Size:    18239748 bytes
```

### 3. Start Android Emulator

Boot your local AVD (e.g. Pixel_6_API_34):

```bash
emulator -avd Pixel_6_API_34 -netdelay none -netspeed full
```

Verify the device is recognized:

```bash
adb devices
```

### 4. Start Appium 3 Server

In a dedicated terminal window:

```bash
appium --port 4723
```

### 5. Run Test Suite

```bash
# Run all 7 test scenarios
pytest -v

# Run with JUnit XML report generation
pytest -v --junitxml=results/junit.xml

# Run only catalog scenarios
pytest -v -m catalog

# Run only shopping cart scenarios
pytest -v -m cart

# Run only authentication scenarios
pytest -v -m auth
```

---

## 6. Available Commands

| Command | Purpose |
|---|---|
| `python scripts/get_apk.py` | Downloads and verifies SHA-256 for the target APK |
| `pytest --collect-only -q` | Discovers all 7 test scenarios without executing |
| `pytest -v` | Executes full mobile test suite with verbose output |
| `ruff check .` | Runs static code analysis and linting across framework |
| `ruff format --check .` | Verifies code formatting compliance |

---

## 7. CI/CD Policy (GitHub Actions)

Workflow file: [`.github/workflows/40-mobile-appium-android.yml`](../.github/workflows/40-mobile-appium-android.yml)

**CI status:** 7 of 7 scenarios passed on the Android 14 (API 34) emulator in [run 42949836540](https://github.com/valarcon1226/qa-automation-portfolio/actions/runs/42949836540).

The automated pipeline executes on push to `40-mobile-appium-android/**` and manually via `workflow_dispatch`:

1. **Hardware Virtualization:** Configures `/dev/kvm` permissions on `ubuntu-latest` for accelerated hardware emulation.
2. **Environment Provisioning:** Configures Java 17, Node.js 20, Python 3.12, and `uv`.
3. **Appium Stack:** Installs pinned Appium 3 (`appium@3.9.0`) and `uiautomator2@8.7.3` driver.
4. **Binary Checksum:** Runs `scripts/get_apk.py` to ensure cryptographic integrity of the APK.
5. **Headless Android 14 Emulator:** Boots `reactivecircus/android-emulator-runner` (API 34 x86_64), initializes Appium server, and executes pytest with `--junitxml`.
6. **Artifact Archiving:** Uploads `artifacts/` (screenshots, page sources, logcat) and JUnit XML reports unconditionally (`if: always()`).
