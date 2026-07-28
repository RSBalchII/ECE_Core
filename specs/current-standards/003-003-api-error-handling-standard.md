# Standard XXX: Global API Error Handling Contract (V5.1+) - Mandatory

**Problem Statement:** 
The system's current global error handling middleware fails to consistently serialize operational errors (like 404 Not Found or 422 Validation Failed) into the expected JSON payload format when underlying services fail during resource lifecycle events (e.g., schema migration). This causes client consumers, especially test suites, to receive non-JSON HTML fallbacks instead of predictable API error codes.

**Solution:**
The top-level Express/Express Middleware must be updated to intercept all framework-level errors (`err`) and explicitly check the context (e.g., checking for specific database error messages like 'No such row' or checking if an expected resource is missing) to manually set appropriate HTTP status codes (404, 422) while ensuring the response body *always* conforms to a standardized JSON format.

**Implementation Details:**
1.  The middleware must be placed **after** all other route/middleware mounting points but **before** any final default handler.
2.  Specific error checks for known operational failures (e.g., `err.message` containing 'deleted') should map to HTTP 404/422 and include a machine-readable message that aids client debugging.

**Testing:**
This standard mandates the creation of an integration test (`migration_error_handling.test.ts`) specifically designed to trigger this fallback path and assert the correct JSON structure, confirming the middleware intercepts framework errors correctly.

**References:**
*   [See also: Standard 051: Pointer-Only Storage](specs/current-standards/data-integrity/051-pointer-only-storage.md) (This failure occurs when resources are deleted as per this standard).
*   [Update Status in specs/spec.md and docs/API.md] (Documentation must reflect this mandatory contract.)