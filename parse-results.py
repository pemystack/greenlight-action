"""Parse JUnit XML test results and output JSON failures."""
import xml.etree.ElementTree as ET
import json
import sys
import os

results_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("RESULTS_PATH", "junit.xml")

failures = []
total = 0
failed = 0

try:
    tree = ET.parse(results_path)
    for suite in list(tree.iter("testsuite")):
        total += int(suite.get("tests", "0"))
        failed += int(suite.get("failures", "0")) + int(suite.get("errors", "0"))
    for tc in tree.iter("testcase"):
        for fail in list(tc.findall("failure")) + list(tc.findall("error")):
            msg = fail.text or fail.get("message", "")
            failures.append({
                "className": tc.get("classname", ""),
                "testName": tc.get("name", ""),
                "failure": msg[:3000],
            })
except Exception:
    pass

result = {"failures": failures[:15], "total": total, "failed": failed}
print(json.dumps(result))
