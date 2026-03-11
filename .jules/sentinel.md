
## 2024-05-24 - Path Traversal Vulnerability in /v1/files/read
**Vulnerability:** Path traversal via weak string inclusion checks (`filePath.includes('distilled')`).
**Learning:** A string inclusion check like `.includes()` or `.indexOf()` is insufficient for path validation because an attacker can embed the required string inside a directory traversal payload (e.g., `../../../distilled/../../../etc/passwd.yaml`).
**Prevention:** Always use `path.resolve()` to get the absolute path, and then use `.startsWith()` to strictly verify that the resolved path begins with the absolute path of the allowed base directory.
