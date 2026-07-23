# Security policy

## Supported versions

ComradBot is in early development. Security fixes are applied only to the latest revision of the
default branch until formal releases and a version support matrix exist.

## Reporting a vulnerability

Do not open a public issue for a vulnerability that could expose credentials, private server data,
local files, authorization checks, or remote code execution.

Use GitHub private vulnerability reporting for this repository when it is available. Include:

- the affected revision and environment;
- a concise description of the impact;
- reproducible steps or a minimal proof of concept;
- relevant logs with all secrets and signed URLs removed;
- any suggested mitigation, if known.

Allow maintainers reasonable time to investigate and publish a fix before public disclosure.

## Sensitive data

Immediately revoke and replace any Discord or OpenAI credential suspected of exposure. ComradBot
must never log or commit tokens, API keys, authentication headers, complete signed stream URLs, or
sensitive conversation content.

## Scope reminders

The project does not support DRM circumvention, private-content access, authentication bypass, voice
cloning, or impersonation of real people. Reports requesting those capabilities are out of scope.
