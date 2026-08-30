# Licensing strategy

**Today:** the entire `holdthedoor` repository — hooks, CLI, policy engine, audit log,
and the current `monitor.py` dashboard — is MIT licensed (see [`LICENSE`](LICENSE)). No
part of the project you can install and run today requires anything other than MIT.

**Planned:** a future, substantially more detailed dashboard/engine component
(working name: `holdthedoor/engine/` — centralized multi-machine views, policy sync
across a team, historical analytics) is planned. When that component ships, it will be
licensed under the [Business Source License 1.1](https://mariadb.com/bsl11/) (BSL-1.1),
following the same model as projects like [caveman](https://github.com/JuliusBrussee/caveman):

- **Free for:** internal evaluation, local development, CI/CD, and self-hosted use —
  including inside a company, for your own team's traffic.
- **Restricted:** offering the licensed component to third parties as a hosted service
  (i.e. reselling it as a SaaS product) requires a commercial agreement with the
  licensor.
- **Change Date:** 4 years after that component's first release. On that date, the
  component automatically relicenses to Apache License 2.0 — fully open source,
  no strings attached.

The rest of the project (everything that exists today) is unaffected and stays MIT
permanently. This split only ever applies to code that does not exist yet; nothing
currently in this repository is covered by BSL.
