A.N.E. AUDIT PACKAGE — SAFE SHARING PROFILE

Baseline: main@61f2da448b234bde0318237965ac954c2c591c17 plus the six opening
frontend modifications.

Included:
- sanitized report copies;
- two new live-scene screenshots produced with SwiftShader;
- redacted/reproducible command evidence;
- dependency scanner JSON containing package metadata only;
- aggregate metrics and a path/hash/size manifest of knowledge/.

Intentionally excluded:
- the text of knowledge/ (authorial product);
- .git and unreachable objects;
- runtime raw data, model outputs and old screenshots;
- secrets.env, .env files, OAuth files, tokens and credential candidates;
- personal absolute paths and author email;
- installed dependencies, caches and builds.

The synthetic candidate values used in credential-leak tests are not stored. Only
boolean matches and lengths are retained.

This package is evidence, not a statement that the repository or its content is
licensed for redistribution.
