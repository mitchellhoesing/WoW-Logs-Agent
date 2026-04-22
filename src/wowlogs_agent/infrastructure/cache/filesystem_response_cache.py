from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class FilesystemResponseCache:
    """Cache GraphQL responses under `<root>/<namespace>/<key>.json`.

    Namespaces are relative paths (forward-slash separated) — typically
    `<reportId>/<query-hash>` as described in CLAUDE.md.
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    def get(self, namespace: str, key: str) -> Mapping[str, Any] | None:
        path = self._path_for(namespace, key)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as fh:
            data: Mapping[str, Any] = json.load(fh)
        return data

    def put(self, namespace: str, key: str, value: Mapping[str, Any]) -> None:
        path = self._path_for(namespace, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(value, fh, indent=2, sort_keys=True)

    def _path_for(self, namespace: str, key: str) -> Path:
        safe_namespace = namespace.replace("\\", "/").strip("/")
        return self._root.joinpath(*safe_namespace.split("/")) / f"{key}.json"
