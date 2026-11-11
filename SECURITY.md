# Security Policy

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

Report it privately through GitHub's
[private vulnerability reporting](https://github.com/whereq/FlowDesktop/security/advisories/new)
on this repository. If that is unavailable to you, open a regular issue that
says only *"security report — please open a private channel"* and nothing
else; you will be asked for details privately.

Please include, as far as you can:

- what the issue is and where in the code it lives,
- how to reproduce it,
- the impact you believe it has,
- any suggested fix.

You should get an acknowledgement within a week. Fixes for confirmed issues are
released as soon as they are ready, and the reporter is credited in the
release notes unless they ask not to be.

## What counts as a vulnerability

- Authentication or authorisation bypass — reaching another user's data, or an
  admin-only surface without the right role.
- Injection — SQL injection, command injection, or prompt injection that lets
  untrusted content take over the assistant.
- Secret exposure — a credential, token or private key committed to the
  repository or baked into an image.
- Unsafe defaults — a deployment that is exposed by default.

## What does not

- The LLM producing a wrong or un-invested answer. That is a product quality
  issue, not a vulnerability.
- Missing hardening you did not ask for. We welcome hardening pull requests.
- Rate-limit or abuse issues in a third-party service.
- Denial of service through sheer request volume against your own deployment.

## Threat model

FlowDesktop is designed to be run by the person who deploys it, on their own
infrastructure. A few consequences worth stating plainly:

**The LLM is untrusted input.** Web pages, filings and other retrieved content
are summarised, never obeyed. The system prompt treats them as data. A prompt
injection in a fetched document should produce a wrong answer at worst, not
code execution.

**The LLM never issues financial advice.** It produces research and analysis.
It is configured not to tell a user to buy, sell, hold or allocate.

**Tools are the trust boundary.** Every tool validates its own arguments.
A tool must never execute a model-supplied shell command, build a SQL string
from model output, or fetch an arbitrary URL without a host allow-list.

**Your deployment is your responsibility.** Put the API behind
authentication, terminate TLS in front of it, and keep the database off the
public internet. The default Compose stack publishes the database port for
local convenience — remove that line for anything reachable from outside.

**The API talks to third parties on your behalf.** With platform mode enabled,
prompts you send are sent to the configured LLM provider. In BYOK mode the
user's own key is used instead. Nothing else leaves your deployment except
the market-data requests the collector makes.

## Hardening notes for operators

- Set a strong `POSTGRES_PASSWORD` and change the default in `docker/.env`.
- Remove the `db` service's published port from `docker/docker-compose.yml`
  unless you need to reach it from the host.
- Set `SEC_USER_AGENT` to a real contact address — the SEC asks automated
  clients to identify themselves.
- Keep `STRIPE_SECRET_KEY`, `KEYCLOAK_ADMIN_CLIENT_SECRET`, `VAPID_PRIVATE_KEY`
  and the LLM keys out of version control. `.env` is gitignored; use your
  platform's secret store where you have one.
- Rotate the database password if this repository was ever deployed with the
  example values in a non-local environment.
