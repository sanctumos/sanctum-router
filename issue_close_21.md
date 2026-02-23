Fixed in PR (see commit below).

**#21 – CLI boolean flags**

`type=bool` was wrong: `bool('false')` is `True`. Implemented `_parse_bool(s)` that parses `true`/`false`/`1`/`0` (case-insensitive); handles `None`/empty for optional `--cost-optimization`.

Applied to:
- `--supports-tools`
- `--supports-streaming`
- `--supports-multimodal`
- `--cost-optimization`

So `--supports-tools false` now correctly sets the flag to False. Version 0.1.7.

(Ada: no additional directive; closing as implemented.)
