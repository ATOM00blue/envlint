"""Diff two parsed env files."""

from __future__ import annotations

from dataclasses import dataclass, field

from .parser import ParsedEnv


@dataclass
class EnvDiff:
    only_in_a: list[str] = field(default_factory=list)
    only_in_b: list[str] = field(default_factory=list)
    # key -> (value_a, value_b) for keys present in both with differing values
    changed: dict[str, tuple[str, str]] = field(default_factory=dict)
    common: list[str] = field(default_factory=list)

    @property
    def has_differences(self) -> bool:
        return bool(self.only_in_a or self.only_in_b or self.changed)


def diff_envs(a: ParsedEnv, b: ParsedEnv) -> EnvDiff:
    """Compute the difference between two parsed env files."""
    map_a = a.as_dict()
    map_b = b.as_dict()
    keys_a = set(map_a)
    keys_b = set(map_b)

    only_a = sorted(keys_a - keys_b)
    only_b = sorted(keys_b - keys_a)
    shared = keys_a & keys_b

    changed: dict[str, tuple[str, str]] = {}
    common: list[str] = []
    for key in sorted(shared):
        if map_a[key] != map_b[key]:
            changed[key] = (map_a[key], map_b[key])
        else:
            common.append(key)

    return EnvDiff(only_in_a=only_a, only_in_b=only_b, changed=changed, common=common)
