import os


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    reports_dir = "reports"
    os.makedirs(reports_dir, exist_ok=True)
    summary_path = os.path.join(reports_dir, "SUMMARY.md")

    passed = len(terminalreporter.stats.get("passed", []))
    failed = len(terminalreporter.stats.get("failed", []))
    xfailed = len(terminalreporter.stats.get("xfailed", []))
    xpassed = len(terminalreporter.stats.get("xpassed", []))
    skipped = len(terminalreporter.stats.get("skipped", []))

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("# Test Summary\n\n")
        f.write(f"- Passed: {passed}\n")
        f.write(f"- Failed: {failed}\n")
        f.write(f"- XFailed: {xfailed}\n")
        f.write(f"- XPassed: {xpassed}\n")
        f.write(f"- Skipped: {skipped}\n\n")
        f.write("## XFailed (Known Bugs)\n")
        for xfail in terminalreporter.stats.get("xfailed", []):
            f.write(f"- {xfail.nodeid}: {xfail.wasxfail}\n")
