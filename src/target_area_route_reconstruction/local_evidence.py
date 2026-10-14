"""M3A basic-local raw/source custody and independently re-ingested M2A reload.

Integrity in a trusted local runtime, not hostile-storage authentication.
No enhanced backend or complete derived GraphCommit is implemented here.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import math
import platform
import sqlite3
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from importlib import metadata
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from ._quality_evidence import evidence_digest
from .ingestion import DEFAULT_SOURCE_BYTES, MAX_SOURCE_BYTES, ingest_bytes, _read_regular_file
from .models import IngestionResult, SourceFailure
from .normalization import NORMALIZER
from .strict_json import loads_json, StrictJSONError

ENCODING = "m3-local-source-v1"
RECORD_BYTES_LIMIT = 16 * 1024 * 1024


class LocalEvidenceError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def canonical_record(value) -> bytes:
    """Native JSON only; normalize exact numeric aliases without rounding."""
    def normalize(item):
        if item is None or type(item) is bool:
            return item
        if type(item) is str:
            item.encode("utf-8", errors="strict")
            return item
        if type(item) is int:
            return item
        if type(item) is float and math.isfinite(item):
            return int(item) if item.is_integer() else item
        if type(item) is list:
            return [normalize(v) for v in item]
        if type(item) is dict and all(type(k) is str for k in item):
            return {normalize(k): normalize(v) for k, v in item.items()}
        raise LocalEvidenceError("M3_JSON_INVALID")
    try:
        return json.dumps(normalize(value), sort_keys=True, ensure_ascii=False,
                          allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise LocalEvidenceError("M3_JSON_INVALID") from exc


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _limit(value):
    if type(value) is not int or not 1 <= value <= MAX_SOURCE_BYTES:
        raise LocalEvidenceError("INVALID_SOURCE_BYTES_LIMIT")


@lru_cache(maxsize=1)
def _source_validator():
    base = "https://schemas.target-area.invalid/v0.1/"
    registry = Registry()
    documents = {}
    for name in ("common", "track-source"):
        document = loads_json(files(__package__).joinpath("spec", name + ".schema.json").read_bytes())
        document["$id"] = base + name + ".schema.json"
        documents[name] = document
        registry = registry.with_resource(document["$id"], Resource.from_contents(document))
    return Draft202012Validator(documents["track-source"], registry=registry, format_checker=FormatChecker())


def _source(source, kind, raw_digest):
    if type(kind) is not str or kind not in ("fit", "gpx"):
        raise LocalEvidenceError("UNSUPPORTED_SOURCE_KIND")
    normalized = loads_json(canonical_record(source))
    if not _source_validator().is_valid(normalized):
        raise LocalEvidenceError("M3_SOURCE_INVALID")
    media = {"gpx": "application/gpx+xml", "fit": "application/vnd.ant.fit"}
    if normalized["representation"]["media_type"] != media[kind]:
        raise LocalEvidenceError("M3_SOURCE_KIND_MISMATCH")
    expected = normalized["representation"].get("content_hash")
    if expected is not None and expected["digest"] != raw_digest:
        raise LocalEvidenceError("SOURCE_HASH_MISMATCH")
    return normalized


def parser_artifacts():
    """Actual M2A package/parser/native bytes; identities exclude install paths.

    Recomputed on verification, not trusted from a mutable version label/cache.
    Complete M2B–M2F historical execution attestation is later M3B work.
    """
    artifacts = {}
    package = Path(__file__).parent
    for path in sorted(package.glob("*.py")):
        artifacts["core/" + path.name] = _sha(path.read_bytes())
    for path in sorted((package / "spec").glob("*")):
        if path.is_file():
            artifacts["spec/" + path.name] = _sha(path.read_bytes())
    for name in ("fitdecode", "lxml", "geographiclib"):
        distribution = metadata.distribution(name)
        for entry in sorted(distribution.files or (), key=str):
            if entry.suffix in (".py", ".so", ".pyd", ".dll", ".dylib") or ".so." in entry.name:
                artifacts[name + "/" + str(entry)] = _sha(Path(distribution.locate_file(entry)).read_bytes())
    for name in ("_datetime", "_decimal", "math", "_elementtree", "_json", "_struct", "_hashlib", "json", "decimal", "datetime", "dataclasses"):
        module = importlib.import_module(name)
        if getattr(module, "__file__", None):
            artifacts["stdlib/" + name] = _sha(Path(module.__file__).read_bytes())
    artifacts["python"] = _sha(Path(sys.executable).read_bytes())
    return {"purpose": "m2a-replay-v1", "python": sys.version, "platform": platform.platform(),
            "artifacts": artifacts}


def _admit_ingestion(evidence):
    # Reuse the audited recursive M2A gate before any snapshot codec/hash.
    try:
        evidence_digest(evidence)
    except ValueError as exc:
        raise LocalEvidenceError("QUALITY_EVIDENCE_INVALID") from exc


def _recipe(kind):
    library = "fitdecode" if kind == "fit" else "lxml"
    parameters = ({"check_crc": "RAISE", "error_handling": "RAISE"} if kind == "fit" else
                  {"resolve_entities": False, "load_dtd": False, "no_network": True, "huge_tree": False})
    return {"parser": {"name": library, "version": metadata.version(library), "parameters": parameters},
            "normalizer": dict(NORMALIZER), "source_kind": kind}


@dataclass(frozen=True)
class SourceAdmission:
    source_id: str
    revision_id: str
    record_digest: str
    raw_digest: str
    outcome: str
    profile: str = "basic-local"


@dataclass(frozen=True)
class SourceReload:
    status: str
    admission: SourceAdmission
    track_source_json: str
    ingestion: IngestionResult | None
    issues: tuple[str, ...] = ()
    verification_scope: str = "source-and-m2a"


class LocalEvidenceStore:
    """SQLite atomic source custody on a trusted local filesystem."""
    def __init__(self, path: str | Path, *, profile: str = "basic-local"):
        if type(profile) is not str or profile != "basic-local":
            raise LocalEvidenceError("trust_backend_unavailable" if profile == "enhanced-custody" else "M3_PROFILE_INVALID")
        self.path = Path(path)
        if str(self.path) == ":memory:":
            raise LocalEvidenceError("M3_STORAGE_PATH_INVALID")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2):
                raise LocalEvidenceError("M3_SCHEMA_UNAVAILABLE")
            if version == 0:
                if db.execute("SELECT count(*) FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchone()[0]:
                    raise LocalEvidenceError("M3_SCHEMA_UNAVAILABLE")
                db.execute("CREATE TABLE blobs (digest TEXT PRIMARY KEY, data BLOB NOT NULL)")
                db.execute("CREATE TABLE admissions (source_id TEXT NOT NULL, revision_id TEXT NOT NULL, record_digest TEXT NOT NULL UNIQUE, raw_digest TEXT NOT NULL REFERENCES blobs(digest), record BLOB NOT NULL, PRIMARY KEY(source_id, revision_id))")
                db.execute("PRAGMA user_version=1")
                db.commit()

    @contextmanager
    def _connect(self):
        db = None
        try:
            db = sqlite3.connect(self.path, timeout=10)
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA journal_mode=DELETE")
            with db:
                yield db
        except sqlite3.Error as exc:
            raise LocalEvidenceError("M3_STORAGE_FAILED") from exc
        finally:
            if db is not None:
                db.close()

    @staticmethod
    def _decode(row):
        if row is None:
            raise LocalEvidenceError("M3_SOURCE_NOT_FOUND")
        sid, revision, digest, raw_digest, payload = row
        try:
            if type(payload) is not bytes or len(payload) > RECORD_BYTES_LIMIT or _sha(payload) != digest:
                raise LocalEvidenceError("M3_STORE_CORRUPT")
            record = loads_json(payload)
            if type(record) is not dict or set(record) != {"encoding", "profile", "source", "source_kind", "raw", "parser_artifacts", "recipe", "ingestion_json"}:
                raise LocalEvidenceError("M3_STORE_CORRUPT")
            if canonical_record(record) != payload or record["encoding"] != ENCODING or record["profile"] != "basic-local":
                raise LocalEvidenceError("M3_STORE_CORRUPT")
            if (record["source"]["id"], record["source"]["revision_id"], record["raw"]["sha256"]) != (sid, revision, raw_digest):
                raise LocalEvidenceError("M3_STORE_CORRUPT")
            return record
        except (KeyError, TypeError, StrictJSONError, RecursionError) as exc:
            raise LocalEvidenceError("M3_STORE_CORRUPT") from exc

    def admit_file(self, path: str | Path, *, source_kind: str, track_source: dict,
                   max_source_bytes: int = DEFAULT_SOURCE_BYTES) -> SourceAdmission:
        """Read bounded regular FIT/GPX files without modifying their bytes."""
        _limit(max_source_bytes)
        try:
            data = _read_regular_file(path, max_source_bytes)
        except SourceFailure as exc:
            raise LocalEvidenceError(exc.diagnostic.code) from exc
        return self.admit_bytes(data, source_kind=source_kind, track_source=track_source,
                                max_source_bytes=max_source_bytes)

    def admit_bytes(self, data: bytes, *, source_kind: str, track_source: dict,
                    max_source_bytes: int = DEFAULT_SOURCE_BYTES) -> SourceAdmission:
        _limit(max_source_bytes)
        if type(data) is not bytes:
            raise LocalEvidenceError("SOURCE_BYTES_REQUIRED")
        if len(data) > max_source_bytes:
            raise LocalEvidenceError("SOURCE_BYTES_LIMIT_EXCEEDED")
        raw_digest = _sha(data)
        source = _source(track_source, source_kind, raw_digest)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT source_id,revision_id,record_digest,raw_digest,CASE WHEN length(record)<=16777216 THEN record ELSE NULL END FROM admissions WHERE source_id=? AND revision_id=?", (source["id"], source["revision_id"])).fetchone()
            if row:
                record = self._decode(row)
                if (record["source"] != source or canonical_record(record["source"]) != canonical_record(source)
                        or record["raw"]["sha256"] != raw_digest or record["source_kind"] != source_kind):
                    raise LocalEvidenceError("M3_SOURCE_CONFLICT")
                self._raw(db, record, max_source_bytes)
                return self._admission(record, row[2])
            ingestion = ingest_bytes(data, source_kind=source_kind,
                                     track_source={"id": source["id"], "revision_id": source["revision_id"]})
            _admit_ingestion(ingestion)
            try:
                artifacts, recipe = parser_artifacts(), _recipe(source_kind)
            except (OSError, metadata.PackageNotFoundError) as exc:
                raise LocalEvidenceError("M3_ARTIFACT_UNAVAILABLE") from exc
            record = {"encoding": ENCODING, "profile": "basic-local", "source": source,
                      "source_kind": source_kind, "raw": {"sha256": raw_digest, "byte_length": len(data)},
                      "parser_artifacts": artifacts, "recipe": recipe, "ingestion_json": ingestion.to_json()}
            encoded = canonical_record(record)
            if len(encoded) > RECORD_BYTES_LIMIT:
                raise LocalEvidenceError("M3_RECORD_LIMIT_EXCEEDED")
            digest = _sha(encoded)
            # Verify any deduplicated blob instead of accepting its name alone.
            blob = db.execute("SELECT length(data) FROM blobs WHERE digest=?", (raw_digest,)).fetchone()
            if blob is not None:
                self._raw(db, record, max_source_bytes)
            else:
                db.execute("INSERT INTO blobs VALUES (?,?)", (raw_digest, data))
            db.execute("INSERT INTO admissions VALUES (?,?,?,?,?)", (source["id"], source["revision_id"], digest, raw_digest, encoded))
            db.commit()
            return self._admission(record, digest)

    @staticmethod
    def _admission(record, digest):
        try:
            outcome = loads_json(record["ingestion_json"])["outcome"]
            if outcome not in ("success", "failure", "no_positioned_observations"):
                raise LocalEvidenceError("M3_STORE_CORRUPT")
            return SourceAdmission(record["source"]["id"], record["source"]["revision_id"], digest, record["raw"]["sha256"], outcome)
        except (KeyError, TypeError, StrictJSONError) as exc:
            raise LocalEvidenceError("M3_STORE_CORRUPT") from exc

    @staticmethod
    def _raw(db, record, budget):
        try:
            raw_digest, size = record["raw"]["sha256"], record["raw"]["byte_length"]
            if type(size) is not int or not 0 <= size <= budget:
                raise LocalEvidenceError("SOURCE_BYTES_LIMIT_EXCEEDED")
            length = db.execute("SELECT length(data),typeof(data) FROM blobs WHERE digest=?", (raw_digest,)).fetchone()
            if length != (size, "blob"):
                raise LocalEvidenceError("M3_STORE_CORRUPT")
            data = db.execute("SELECT data FROM blobs WHERE digest=?", (raw_digest,)).fetchone()[0]
            if _sha(data) != raw_digest:
                raise LocalEvidenceError("M3_STORE_CORRUPT")
            return data
        except (KeyError, TypeError) as exc:
            raise LocalEvidenceError("M3_STORE_CORRUPT") from exc

    def _material(self, source_id: str, revision_id: str, *, expected_record_digest: str,
                      max_source_bytes: int = DEFAULT_SOURCE_BYTES):
        """Read one expected source/root snapshot, independently of old artifacts."""
        _limit(max_source_bytes)
        if (any(type(v) is not str or not v for v in (source_id, revision_id, expected_record_digest))
                or len(expected_record_digest) != 64 or any(c not in "0123456789abcdef" for c in expected_record_digest)):
            raise LocalEvidenceError("M3_EXPECTED_RECORD_INVALID")
        with self._connect() as db:
            # One SQLite read snapshot prevents independent record/blob queries racing.
            db.execute("BEGIN")
            row = db.execute("SELECT source_id,revision_id,record_digest,raw_digest,CASE WHEN length(record)<=16777216 THEN record ELSE NULL END FROM admissions WHERE source_id=? AND revision_id=?", (source_id, revision_id)).fetchone()
            record = self._decode(row)
            if row[2] != expected_record_digest:
                raise LocalEvidenceError("M3_EXPECTED_RECORD_MISMATCH")
            data = self._raw(db, record, max_source_bytes)
        _source(record["source"], record["source_kind"], record["raw"]["sha256"])
        return record, row[2], data

    def reload_source(self, source_id: str, revision_id: str, *, expected_record_digest: str,
                      max_source_bytes: int = DEFAULT_SOURCE_BYTES) -> SourceReload:
        """Compare explicit expected admission, raw integrity and fresh M2A replay."""
        record, digest, data = self._material(source_id, revision_id,
            expected_record_digest=expected_record_digest, max_source_bytes=max_source_bytes)
        source = _source(record["source"], record["source_kind"], record["raw"]["sha256"])
        admission = self._admission(record, digest)
        source_json = canonical_record(source).decode("utf-8")
        try:
            current_artifacts = parser_artifacts()
            current_recipe = _recipe(record["source_kind"])
        except (OSError, metadata.PackageNotFoundError):
            return SourceReload("historical_unverified", admission, source_json, None, ("artifact_unavailable",))
        if record["parser_artifacts"] != current_artifacts:
            return SourceReload("historical_unverified", admission, source_json, None, ("artifact_digest_mismatch",))
        if record["recipe"] != current_recipe:
            return SourceReload("historical_unverified", admission, source_json, None, ("algorithm_recipe_mismatch",))
        ingestion = ingest_bytes(data, source_kind=record["source_kind"],
                                 track_source={"id": source_id, "revision_id": revision_id})
        _admit_ingestion(ingestion)
        if ingestion.to_json() != record["ingestion_json"]:
            raise LocalEvidenceError("M3_REINGEST_MISMATCH")
        return SourceReload("verified_local", admission, source_json, ingestion)
