import json
import os
from pathlib import Path


def get_actionable_report():
    results_path = Path(".lighthouseci/assertion-results.json")
    if not results_path.exists():
        print("No assertion results found. Run `npm run lighthouse:ci` first.")
        return

    with open(results_path) as f:
        assertions = json.load(f)

    failures = [a for a in assertions if not a["passed"]]
    if not failures:
        print("✅ No performance regressions found!")
        return

    report_lines = []
    report_lines.append("# Lighthouse Performance Report (Actionable)")
    report_lines.append(f"\nFound {len(failures)} failures that need resolution.\n")

    # Group by URL
    by_url = {}
    for failure in failures:
        url = failure["url"]
        if url not in by_url:
            by_url[url] = []
        by_url[url].append(failure)

    lhr_files = sorted(
        Path(".lighthouseci").glob("lhr-*.json"), key=os.path.getmtime, reverse=True
    )

    for url, url_failures in by_url.items():
        report_lines.append(f"## URL: {url}")

        # Find the latest LHR for this URL
        current_lhr = None
        for lhr_file in lhr_files:
            try:
                with open(lhr_file) as f:
                    lhr = json.load(f)
                    if lhr["finalUrl"] == url:
                        current_lhr = lhr
                        break
            except Exception:
                continue

        for failure in url_failures:
            audit_id = failure.get("auditId")
            audit_property = failure.get("auditProperty")
            name = failure.get("auditTitle") or audit_id or audit_property

            report_lines.append(f"### ❌ {name}")
            report_lines.append(f"- **Metric**: {audit_id}")
            report_lines.append(
                f"- **Expected**: {failure['expected']} {failure.get('operator', '')}"
            )
            report_lines.append(f"- **Actual**: {failure['actual']}")

            if current_lhr:
                audit = current_lhr.get("audits", {}).get(audit_id)
                if audit:
                    desc = audit.get("description", "")
                    # Remove markdown links for cleaner output in some contexts
                    report_lines.append(f"- **Description**: {desc}")
                    if "displayValue" in audit:
                        report_lines.append(f"- **Value**: {audit['displayValue']}")

                    # Actionable Details
                    details = audit.get("details", {})
                    if details.get("items"):
                        report_lines.append("- **Actionable Items**:")
                        for item in details["items"][:5]:  # top 5
                            # Try to extract useful info from the dictionary
                            item_str = str(item)
                            if isinstance(item, dict):
                                if "node" in item:
                                    node_info = item["node"]
                                    item_str = f"Element: `{node_info.get('snippet', node_info.get('selector'))}`"
                                    if "score" in item:
                                        item_str += (
                                            f" (Impact: {item.get('score'):.3f})"
                                        )
                                elif "url" in item:
                                    item_str = f"Resource: {item['url']}"
                                    if "totalBytes" in item:
                                        item_str += (
                                            f" ({item['totalBytes'] // 1024} KB)"
                                        )
                                elif "label" in item:
                                    item_str = f"{item['label']}: {item.get('value')}"
                                else:
                                    # Fallback: just show the keys that might be interesting
                                    interesting_keys = ["reason", "message", "subItems"]
                                    found_keys = [
                                        f"{k}: {item[k]}"
                                        for k in interesting_keys
                                        if k in item
                                    ]
                                    if found_keys:
                                        item_str = ", ".join(found_keys)
                            report_lines.append(f"  - {item_str}")
            report_lines.append("")

        report_lines.append("\n---\n")

    report_content = "\n".join(report_lines)

    # Save to a file for the agent to read
    with open("perf_report.md", "w") as f:
        f.write(report_content)

    # Also print to stdout for immediate feedback
    print(report_content)
    print("\nActionable report saved to: perf_report.md")


if __name__ == "__main__":
    get_actionable_report()
