
## 2025-03-22 - Path Traversal Vulnerability in Backup Service
**Vulnerability:** Path Traversal via the `filename` parameter in backup endpoints (`/v1/backup/restore` and `/v1/backups`). An attacker could supply `../../../etc/passwd` to validateBackup or restoreBackup, allowing them to verify file existence and read arbitrary file content sizes/metadata outside the intended backup directory.
**Learning:** Functions accepting filenames from API requests must always treat them as untrusted input. Directly joining a base directory with an untrusted filename (`path.join(DIR, filename)`) is an anti-pattern unless `filename` has been strictly sanitized.
**Prevention:** Always sanitize the user-provided filename input using `path.basename(filename)` *before* joining it with base directories, ensuring no path components (`../`, etc.) remain.
