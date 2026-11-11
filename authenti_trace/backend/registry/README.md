# Threat registries (empty on purpose)

The Integrity and Network checks compare files with these lists. **While a list is empty, its check carries no
weight** (it does not count as "clean"). Add real entries from sources you trust.

| File | One value per line | Matches |
|---|---|---|
| `malicious_sha256.txt` | SHA-256 of a file (64 hex characters) | the exact same file |
| `synthetic_dhash.txt` | 64-bit perceptual hash (16 hex characters, as in a report's `dhash_hex`) | the same image after resizing or re-compression (within `DHASH_MAX_DISTANCE` bits, default 4) |

Lines may carry a `# comment`. Restart the API after editing. Do not put user media or personal data here: only hashes.
Where entries come from (your own confirmed incidents, a threat-intelligence feed you license) is your decision.
