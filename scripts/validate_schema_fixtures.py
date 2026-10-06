#!/usr/bin/env python3
"""Validate Milestone 1 fixtures against JSON Schema Draft 2020-12.

The runner treats tests/fixtures/manifest.json as the source of expected
schema-validity outcomes. It validates every schema document first, resolves
repository-relative $ref values, validates each fixture with format checking
enabled, and fails when actual schema validity differs from the manifest.

Semantic expectations such as expect_semantic_valid and expect_assessable are
intentionally reported but not evaluated here. They belong to the separate
semantic-validation layer.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource, Unresolvable


@dataclass(frozen=True)
class FixtureResult:
    path: Path
    schema_path: Path
    expected_valid: bool
    actual_valid: bool
    errors: tuple[ValidationError, ...]
    semantic_expected: bool | None
    assessable_expected: bool | None

    @property
    def expectation_matched(self) -> bool:
        return self.expected_valid == self.actual_valid


class RunnerError(RuntimeError):
    """Raised for repository/manifest errors that prevent validation."""


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise RunnerError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RunnerError(
            f"invalid JSON: {path}:{exc.lineno}:{exc.colno}: {exc.msg}"
        ) from exc


def normalize_schema_for_registry(path: Path, document: dict[str, Any]) -> dict[str, Any]:
    """Add an in-memory base $id when the source schema intentionally omits one.

    Repository schemas use relative $ref paths during development. A file URI
    base lets the standards-based referencing implementation resolve those
    references without modifying the checked-in schema document.
    """

    normalized = dict(document)
    normalized.setdefault("$id", path.resolve().as_uri())
    return normalized


def schema_documents(schema_dir: Path) -> dict[Path, dict[str, Any]]:
    documents: dict[Path, dict[str, Any]] = {}
    for path in sorted(schema_dir.glob("*.schema.json")):
        raw = load_json(path)
        if not isinstance(raw, dict):
            raise RunnerError(f"schema root must be an object: {path}")
        normalized = normalize_schema_for_registry(path, raw)
        try:
            Draft202012Validator.check_schema(normalized)
        except SchemaError as exc:
            raise RunnerError(
                f"invalid Draft 2020-12 schema: {path}: {exc.message}"
            ) from exc
        documents[path.resolve()] = normalized

    if not documents:
        raise RunnerError(f"no *.schema.json files found under {schema_dir}")
    return documents


def build_registry(documents: dict[Path, dict[str, Any]]) -> Registry:
    registry = Registry()
    for path, document in documents.items():
        uri = path.as_uri()
        registry = registry.with_resource(uri, Resource.from_contents(document))
    return registry


def json_path(error: ValidationError) -> str:
    if not error.absolute_path:
        return "$"

    chunks: list[str] = ["$"]
    for part in error.absolute_path:
        if isinstance(part, int):
            chunks.append(f"[{part}]")
        else:
            escaped = str(part).replace("\\", "\\\\").replace('"', '\\"')
            chunks.append(f'["{escaped}"]')
    return "".join(chunks)


def schema_path(error: ValidationError) -> str:
    if not error.absolute_schema_path:
        return "#"
    return "#/" + "/".join(str(part) for part in error.absolute_schema_path)


def sort_errors(errors: Iterable[ValidationError]) -> tuple[ValidationError, ...]:
    return tuple(
        sorted(
            errors,
            key=lambda error: (
                tuple(str(part) for part in error.absolute_path),
                tuple(str(part) for part in error.absolute_schema_path),
                error.message,
            ),
        )
    )


def resolve_manifest_schema(repo_root: Path, fixture_path: Path, raw_schema: str) -> Path:
    candidate = (fixture_path.parent / raw_schema).resolve()
    try:
        candidate.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise RunnerError(
            f"manifest schema path escapes repository: {raw_schema!r} "
            f"for fixture {fixture_path}"
        ) from exc
    return candidate


def resolve_manifest_fixture(repo_root: Path, fixtures_root: Path, raw_path: str) -> Path:
    candidate = (fixtures_root / raw_path).resolve()
    try:
        candidate.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise RunnerError(
            f"manifest fixture path escapes repository: {raw_path!r}"
        ) from exc
    return candidate


def validate_fixture(
    *,
    fixture_path: Path,
    schema_path_: Path,
    expected_valid: bool,
    semantic_expected: bool | None,
    assessable_expected: bool | None,
    documents: dict[Path, dict[str, Any]],
    registry: Registry,
    format_checker: FormatChecker,
) -> FixtureResult:
    if schema_path_ not in documents:
        raise RunnerError(
            f"manifest references schema outside loaded schema set: {schema_path_}"
        )

    instance = load_json(fixture_path)
    schema = documents[schema_path_]
    validator = Draft202012Validator(
        schema,
        registry=registry,
        format_checker=format_checker,
    )
    try:
        errors = sort_errors(validator.iter_errors(instance))
    except (NoSuchResource, Unresolvable) as exc:
        raise RunnerError(
            f"failed to resolve schema reference while validating {fixture_path}: {exc}"
        ) from exc

    return FixtureResult(
        path=fixture_path,
        schema_path=schema_path_,
        expected_valid=expected_valid,
        actual_valid=not errors,
        errors=errors,
        semantic_expected=semantic_expected,
        assessable_expected=assessable_expected,
    )


def parse_manifest(repo_root: Path, manifest_path: Path) -> list[dict[str, Any]]:
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        raise RunnerError("fixture manifest root must be an object")

    if manifest.get("schema_version") != "0.1.0":
        raise RunnerError(
            "fixture manifest schema_version must be exactly '0.1.0'"
        )

    entries = manifest.get("fixtures")
    if not isinstance(entries, list):
        raise RunnerError("fixture manifest 'fixtures' must be an array")

    seen: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise RunnerError(f"fixture manifest entry {index} must be an object")

        for key in ("path", "schema", "expect_schema_valid"):
            if key not in entry:
                raise RunnerError(
                    f"fixture manifest entry {index} is missing required key {key!r}"
                )

        raw_path = entry["path"]
        raw_schema = entry["schema"]
        expected = entry["expect_schema_valid"]

        if not isinstance(raw_path, str) or not raw_path:
            raise RunnerError(f"fixture manifest entry {index} has invalid 'path'")
        if not isinstance(raw_schema, str) or not raw_schema:
            raise RunnerError(f"fixture manifest entry {index} has invalid 'schema'")
        if not isinstance(expected, bool):
            raise RunnerError(
                f"fixture manifest entry {index} 'expect_schema_valid' must be boolean"
            )

        if raw_path in seen:
            raise RunnerError(f"duplicate fixture manifest path: {raw_path}")
        seen.add(raw_path)

    return entries


def render_result(result: FixtureResult, repo_root: Path, verbose: bool) -> None:
    fixture_rel = result.path.relative_to(repo_root)
    expected = "valid" if result.expected_valid else "invalid"
    actual = "valid" if result.actual_valid else "invalid"
    status = "PASS" if result.expectation_matched else "FAIL"

    print(f"{status:4} {fixture_rel}  expected={expected} actual={actual}")

    show_errors = verbose or not result.expectation_matched
    if show_errors and result.errors:
        for error in result.errors:
            print(
                f"     {json_path(error)}: {error.message} "
                f"(schema {schema_path(error)})"
            )

    if verbose:
        annotations: list[str] = []
        if result.semantic_expected is not None:
            annotations.append(
                "expect_semantic_valid="
                + str(result.semantic_expected).lower()
            )
        if result.assessable_expected is not None:
            annotations.append(
                "expect_assessable="
                + str(result.assessable_expected).lower()
            )
        if annotations:
            print("     deferred: " + ", ".join(annotations))


def run(repo_root: Path, manifest_path: Path, verbose: bool) -> int:
    schema_dir = repo_root / "schemas"
    fixtures_root = manifest_path.parent

    documents = schema_documents(schema_dir)
    registry = build_registry(documents)
    entries = parse_manifest(repo_root, manifest_path)
    format_checker = FormatChecker()

    results: list[FixtureResult] = []

    for entry in entries:
        fixture_path = resolve_manifest_fixture(
            repo_root, fixtures_root, entry["path"]
        )
        schema_path_ = resolve_manifest_schema(
            repo_root, fixture_path, entry["schema"]
        )

        semantic_expected = entry.get("expect_semantic_valid")
        if semantic_expected is not None and not isinstance(semantic_expected, bool):
            raise RunnerError(
                f"{entry['path']}: expect_semantic_valid must be boolean when present"
            )

        assessable_expected = entry.get("expect_assessable")
        if assessable_expected is not None and not isinstance(assessable_expected, bool):
            raise RunnerError(
                f"{entry['path']}: expect_assessable must be boolean when present"
            )

        result = validate_fixture(
            fixture_path=fixture_path,
            schema_path_=schema_path_,
            expected_valid=entry["expect_schema_valid"],
            semantic_expected=semantic_expected,
            assessable_expected=assessable_expected,
            documents=documents,
            registry=registry,
            format_checker=format_checker,
        )
        results.append(result)
        render_result(result, repo_root, verbose)

    matched = sum(result.expectation_matched for result in results)
    total = len(results)
    failed = total - matched

    print()
    print(
        f"Schema fixture expectations: {matched}/{total} matched; "
        f"{failed} mismatch(es)."
    )
    print(
        f"Schema documents checked as Draft 2020-12: {len(documents)}."
    )

    semantic_pending = sum(
        result.semantic_expected is not None for result in results
    )
    assessable_pending = sum(
        result.assessable_expected is not None for result in results
    )
    if semantic_pending or assessable_pending:
        print(
            "Semantic-layer annotations not evaluated by this runner: "
            f"expect_semantic_valid={semantic_pending}, "
            f"expect_assessable={assessable_pending}."
        )

    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate tests/fixtures/manifest.json expectations using "
            "JSON Schema Draft 2020-12."
        )
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("tests/fixtures/manifest.json"),
        help="fixture expectation manifest (default: tests/fixtures/manifest.json)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="show validation errors for expected-invalid fixtures and semantic annotations",
    )
    args = parser.parse_args(argv)

    script_path = Path(__file__).resolve()
    repo_root = script_path.parent.parent
    manifest_path = args.manifest
    if not manifest_path.is_absolute():
        manifest_path = (repo_root / manifest_path).resolve()

    try:
        return run(repo_root, manifest_path, args.verbose)
    except RunnerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
