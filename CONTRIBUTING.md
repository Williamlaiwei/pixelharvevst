# Contributing

Use Python 3.12 and the hashed development lock. Run Ruff, unit/integration tests and the publication scanner before proposing a change; see README commands. Generate fixtures locally from synthetic data. Do not add external website fixtures, scraped content, real cookie files, private configurations or downloaded image collections.

Keep a single execution path for downloading and checkpointing. Test changes through injected transports, clocks, sleeps or callbacks when possible, then use the local HTTP fixture for behavior that mocks cannot establish. Browser behavior must also be checked against a real local Chromium page.

No public submission is requested until the owner confirms release rights and the effective license. A proposed license file does not grant those rights.

To update locks using uv 0.13.9:

```bash
uv pip compile pyproject.toml --python-version 3.12 --extra browser --generate-hashes -o requirements.lock
uv pip compile pyproject.toml --python-version 3.12 --extra browser --extra dev --generate-hashes -o requirements-dev.lock
```

Commit a lock update with its reason and validation. Browser downloads have separate distribution/licensing considerations and are not vendored here.
