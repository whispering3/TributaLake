from __future__ import annotations

from dataclasses import dataclass

from fiscal_spec.models import FieldSpec, LayoutSpec


@dataclass(frozen=True, slots=True)
class FieldChange:
    record_code: str
    field_name: str
    before: FieldSpec | None
    after: FieldSpec | None


@dataclass(frozen=True, slots=True)
class SpecDiff:
    added_records: tuple[str, ...]
    removed_records: tuple[str, ...]
    changed_fields: tuple[FieldChange, ...]

    def is_empty(self) -> bool:
        return not (self.added_records or self.removed_records or self.changed_fields)


def diff_specs(previous: LayoutSpec, current: LayoutSpec) -> SpecDiff:
    _ensure_same_module(previous, current)
    previous_codes = set(previous.records)
    current_codes = set(current.records)
    changed_fields = tuple(
        change
        for code in sorted(previous_codes & current_codes)
        for change in _field_changes(
            previous.records[code].fields, current.records[code].fields, code
        )
    )
    return SpecDiff(
        added_records=tuple(sorted(current_codes - previous_codes)),
        removed_records=tuple(sorted(previous_codes - current_codes)),
        changed_fields=changed_fields,
    )


def _ensure_same_module(previous: LayoutSpec, current: LayoutSpec) -> None:
    if previous.module != current.module:
        raise ValueError("Só é possível comparar specs do mesmo módulo fiscal.")


def _field_changes(
    previous: tuple[FieldSpec, ...], current: tuple[FieldSpec, ...], record_code: str
) -> tuple[FieldChange, ...]:
    before_by_name = {field.name: field for field in previous}
    after_by_name = {field.name: field for field in current}
    return tuple(
        FieldChange(record_code, name, before_by_name.get(name), after_by_name.get(name))
        for name in sorted(set(before_by_name) | set(after_by_name))
        if before_by_name.get(name) != after_by_name.get(name)
    )
