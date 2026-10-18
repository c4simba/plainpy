"""requests' data structures: CaseInsensitiveDict, the headers of requests and responses."""
from _ppy_typing import TypeVar

_M = TypeVar("_M")                      # (update(): a dict[str, str] or a CaseInsensitiveDict)


class CaseInsensitiveDict:
    """A dict of str keys and values looked up without regard to case (Content-Type is content-type);
    iterating gives the keys as last set."""

    def __init__(self, data: dict[str, str] | None = None) -> None:
        self._store: dict[str, tuple[str, str]] = {}
        if data is not None:
            for k in data:
                self[k] = data[k]

    def __setitem__(self, key: str, value: str) -> None:
        self._store[key.lower()] = (key, value)

    def __getitem__(self, key: str) -> str:
        return self._store[key.lower()][1]

    def __delitem__(self, key: str) -> None:
        del self._store[key.lower()]

    def __contains__(self, key: str) -> bool:
        return key.lower() in self._store

    def __len__(self) -> int:
        return len(self._store)

    def __iter__(self):
        for k in list(self._store):
            yield self._store[k][0]

    def _add(self, key: str, value: str) -> None:
        """value added to key's (joined with ", ", as a response's repeated headers are); the key's first case kept."""
        k = key.lower()
        if k in self._store:
            old = self._store[k]
            self._store[k] = (old[0], old[1] + ", " + value)
        else:
            self._store[k] = (key, value)

    def get(self, key: str, default: str | None = None) -> str | None:
        k = key.lower()
        if k in self._store:
            return self._store[k][1]
        return default

    def pop(self, key: str, default: str | None = None) -> str | None:
        k = key.lower()
        if k in self._store:
            v = self._store[k][1]
            del self._store[k]
            return v
        return default

    def setdefault(self, key: str, default: str) -> str:
        k = key.lower()
        if k not in self._store:
            self._store[k] = (key, default)
        return self._store[k][1]

    def update(self, other: _M) -> None:
        """The keys and values of other (a dict or a CaseInsensitiveDict) set here."""
        if isinstance(other, CaseInsensitiveDict):
            for k, v in other.items():
                self[k] = v
        else:
            for k in other:
                self[k] = other[k]

    def keys(self) -> list[str]:
        return [kv[0] for kv in self._store.values()]

    def values(self) -> list[str]:
        return [kv[1] for kv in self._store.values()]

    def items(self) -> list[tuple[str, str]]:
        return [kv for kv in self._store.values()]

    def lower_items(self) -> list[tuple[str, str]]:
        return [(k, self._store[k][1]) for k in self._store]

    def clear(self) -> None:
        self._store = {}

    def copy(self) -> "CaseInsensitiveDict":
        c = CaseInsensitiveDict()
        for k, v in self.items():
            c[k] = v
        return c

    def __eq__(self, other) -> bool:
        if isinstance(other, CaseInsensitiveDict):
            return sorted(self.lower_items()) == sorted(other.lower_items())
        return False

    def __repr__(self) -> str:
        return "{" + ", ".join(repr(k) + ": " + repr(v) for k, v in self.items()) + "}"
