# Security Policy

## Reporting a Vulnerability

Please do not report security vulnerabilities through public GitHub issues.

Use GitHub's private vulnerability reporting feature if it is enabled for this
repository. Open the repository's Security tab and select "Report a
vulnerability".

If private vulnerability reporting is unavailable, contact the repository
maintainers privately through GitHub. Do not publish vulnerability details
until the maintainers have had an opportunity to investigate.

When reporting a vulnerability, include:

- A description of the affected component and potential impact.
- Steps to reproduce the issue.
- The affected version or commit, if known.
- Any suggested mitigation, if available.

Please do not include real API keys, passwords, personal data, or sensitive
production uploads in your report.

## Scope and Security Considerations

audiodoc is a FastAPI service that accepts untrusted audio and document uploads
for processing. Security reports concerning the following areas are
particularly welcome:

- Authentication, authorization, and API key handling.
- Upload validation, file size limits, and content-type handling.
- Parser, OCR, and document-processing vulnerabilities.
- Path traversal, arbitrary file access, and unsafe temporary files.
- Command injection and unsafe subprocess execution.
- Denial of service through malformed or resource-intensive uploads.
- Exposure of secrets, extracted document contents, or sensitive logs.

## Safe Testing

Only test systems and deployments you own or have explicit permission to
assess. Use synthetic or non-sensitive files when testing upload handling.
Avoid actions that disrupt service availability, access other users' data,
or modify production files.
