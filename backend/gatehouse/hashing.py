"""Action hashing: ties an approval to the exact tool + arguments it covers.

Changing any argument changes the hash, which automatically invalidates any prior
approval for the old hash — no special-case "did the args change" code needed
anywhere else in the system.
"""
import hashlib
import json


def compute_action_hash(tool: str, arguments: dict) -> str:
    canonical = json.dumps({"tool": tool, "arguments": arguments}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
