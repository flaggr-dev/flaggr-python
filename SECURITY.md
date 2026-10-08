# Security Policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | Yes       |

## Reporting a vulnerability

Please don't report security vulnerabilities in public GitHub issues.

Email **security@flaggr.dev**, or report it privately through [GitHub's private vulnerability reporting](https://github.com/flaggr-dev/flaggr-python/security/advisories/new), with:

- a description of the vulnerability
- steps to reproduce it
- its potential impact
- a suggested fix, if you have one

We acknowledge reports within 48 hours and coordinate disclosure with you once a fix is available.

## Using the SDK safely

- Use a project API token with only the read permission for evaluation.
- Keep tokens out of source code: load them from the environment or a secret store.
- Rotate tokens regularly, and revoke a token as soon as it may have leaked.
