"""M3B typed basic-local graph commitments; fresh verified replay, no hydration."""
from __future__ import annotations

import json
import ctypes
import sys
import os
from dataclasses import asdict, dataclass, replace
from importlib import metadata
from pathlib import Path

from ._canonical_snapshot import EVIDENCE_TYPES, SPATIAL_TYPES, canonical_snapshot
from .local_evidence import (
    LocalEvidenceStore, LocalEvidenceError, canonical_record, parser_artifacts,
    RECORD_BYTES_LIMIT, _sha, _admit_ingestion, _recipe,
)
from .strict_json import loads_json, StrictJSONError
from .ingestion import DEFAULT_SOURCE_BYTES, ingest_bytes
from .resource_limits import (
    DEFAULT_TASK_RESOURCE_PROFILE, TaskResourceProfile, DEFAULT_TARGET_VERTICES,
    DEFAULT_OUTPUT_VERTICES,
    normalize_task_resource_profile,
)
from .quality import project_quality
from .quality_verifier import verify_quality
from .quality_models import QualityPolicy, ParentReference, QualityResult, QualityIssue, QualityVerification, QualityAlgorithm, QualityParameters
from ._spatial_inputs import algorithm as spatial_algorithm
from ._m2d_common import M2D_NAME, M2D_VERSION, IDENTITY_POLICY, SNAPSHOT_POLICY
from .spatial import prove_spatial_relation
from .spatial_verifier import verify_spatial_relation
from .spatial_models import SpatialResult, SpatialIssue, SpatialVerification
from .spatial_entities import assemble_spatial_entities
from .spatial_entities_verifier import verify_spatial_entities
from .spatial_entities_models import SpatialAssemblyResult, SpatialEntityBundle, SpatialEntityIssue, SpatialEntityVerification
from .geojson_export import export_geojson, GeoJSONExportResult, GeoJSONIssue
from .temporal_overlay import export_temporal_geojson, ALGORITHM as TEMPORAL_ALGORITHM

ENCODING = "m3-local-graph-v2"
LEGACY_ENCODING = "m3-local-graph-v1"
KINDS = ("request", "M2A", "M2B", "M2C", "M2D", "M2E", "M2F")
TYPES = EVIDENCE_TYPES | SPATIAL_TYPES | frozenset((
    QualityResult, QualityIssue, QualityVerification, SpatialResult, SpatialIssue,
    SpatialVerification, SpatialAssemblyResult, SpatialEntityBundle, SpatialEntityIssue,
    SpatialEntityVerification, GeoJSONExportResult, GeoJSONIssue,
))


def _wire(model):
    if not canonical_snapshot(model, TYPES):
        raise LocalEvidenceError("M3_STAGE_NONCANONICAL")
    return json.dumps(asdict(model), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _target_vertices(area, *, limit=None):
    """Count Polygon/MultiPolygon coordinates iteratively before JSON/GEOS work."""
    if limit is None:
        limit = DEFAULT_TARGET_VERTICES
    if type(area) is not dict:
        return 0
    geometry = area.get("geometry")
    if type(geometry) is not dict:
        return 0
    kind = geometry.get("type")
    depth = {"Polygon": 2, "MultiPolygon": 3}.get(kind)
    coordinates = geometry.get("coordinates")
    if depth is None or type(coordinates) is not list:
        return 0
    visited = count = 0
    stack = [(iter((coordinates,)), 0)]
    while stack:
        children, level = stack[-1]
        try:
            item = next(children)
        except StopIteration:
            stack.pop()
            continue
        visited += 1
        if visited > limit * 4 + 1024:
            raise LocalEvidenceError("TARGET_COMPLEXITY_LIMIT_EXCEEDED")
        if level == depth:
            count += 1
            if count > limit:
                raise LocalEvidenceError("TARGET_COMPLEXITY_LIMIT_EXCEEDED")
        elif type(item) is list:
            stack.append((iter(item), level + 1))
    return count


def _output_vertices(bundle, *, limit=None, initial=0):
    if limit is None:
        limit = DEFAULT_OUTPUT_VERTICES
    count = initial
    if count > limit:
        raise LocalEvidenceError("OUTPUT_LIMIT_EXCEEDED")
    for encoded in bundle.segment_json:
        segment = loads_json(encoded)
        coordinates = segment["geometry"]["coordinates"]
        count += len(coordinates)
        if count > limit:
            raise LocalEvidenceError("OUTPUT_LIMIT_EXCEEDED")
    return count


def _request(area, policy, outside, mode, resource_profile=DEFAULT_TASK_RESOURCE_PROFILE):
    if type(policy) is not QualityPolicy or not canonical_snapshot(policy, TYPES):
        raise LocalEvidenceError("QUALITY_POLICY_INVALID")
    if type(outside) is not bool or (mode is not None and (type(mode) is not str or mode not in ("speed_mps", "pace_s_per_km"))):
        raise LocalEvidenceError("M3_GRAPH_OPTIONS_INVALID")
    # Count geometry vertices before canonical serialization and GEOS conversion.
    limits = normalize_task_resource_profile(resource_profile)
    _target_vertices(area, limit=limits["max_target_vertices"])
    # Native finite target JSON before any polymorphic copy or GEOS conversion.
    target = loads_json(canonical_record(area))
    if type(target) is not dict or any(type(target.get(k)) is not str or not target[k] for k in ("id", "revision_id")):
        raise LocalEvidenceError("M3_TARGET_INVALID")
    return loads_json(canonical_record({"target_area": target, "quality_policy": asdict(policy),
                                       "include_outside": outside, "temporal_mode": mode,
                                       "resource_profile": limits}))


def graph_artifacts():
    artifacts = parser_artifacts()
    artifacts["purpose"] = "m2a-m2f-replay-v1"
    # Hash the ELF that actually supplies CPython, whether statically embedded
    # or shared. Relocated builds may advertise a stale/unloaded LIBDIR.
    if sys.platform.startswith("linux"):
        class DlInfo(ctypes.Structure):
            _fields_ = [("filename", ctypes.c_char_p), ("base", ctypes.c_void_p),
                        ("symbol", ctypes.c_char_p), ("address", ctypes.c_void_p)]
        try:
            resolver = ctypes.CDLL(None).dladdr
        except (AttributeError, OSError) as exc:
            raise OSError("python_implementation_unavailable") from exc
        resolver.argtypes = (ctypes.c_void_p, ctypes.POINTER(DlInfo))
        resolver.restype = ctypes.c_int
        info = DlInfo()
        if not resolver(ctypes.cast(ctypes.pythonapi.Py_GetVersion, ctypes.c_void_p), ctypes.byref(info)) or not info.filename:
            raise OSError("python_implementation_unavailable")
        implementation = Path(os.fsdecode(info.filename))
        artifacts["artifacts"]["python/implementation"] = _sha(implementation.read_bytes())
    else:
        raise OSError("graph_artifact_platform_unavailable")
    for name in ("shapely", "numpy", "jsonschema", "referencing", "jsonschema-specifications", "rpds-py", "attrs",
                 "rfc3339-validator", "rfc3987", "fqdn", "jsonpointer", "webcolors", "idna", "uri-template",
                 "isoduration", "arrow", "python-dateutil", "tzdata", "six", "typing-extensions"):
        dist = metadata.distribution(name)
        for entry in sorted(dist.files or (), key=str):
            if entry.suffix in (".py", ".so", ".pyd", ".dll", ".dylib", ".json") or ".so." in entry.name:
                artifacts["artifacts"][name + "/" + str(entry)] = _sha(Path(dist.locate_file(entry)).read_bytes())
    return artifacts


@dataclass(frozen=True)
class GraphCommit:
    graph_digest: str
    source_record_digest: str
    request_digest: str
    outcome: str
    profile: str = "basic-local"


@dataclass(frozen=True)
class GraphReload:
    status: str
    commit: GraphCommit
    manifest_json: str | None
    issues: tuple[str, ...] = ()
    verification_scope: str = "m2a-m2f"


def _node(kind, parents, payload):
    item = {"kind": kind, "parents": list(parents), "payload_json":
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)}
    return {**item, "sha256": _sha(canonical_record(item))}


def _pipeline(record, source_digest, raw, request, artifacts, *, max_source_bytes=DEFAULT_TASK_RESOURCE_PROFILE.max_source_bytes):
    source = record["source"]
    nodes = []
    def add(kind, payload):
        nodes.append(_node(kind, [source_digest, *(n["sha256"] for n in nodes)], payload))
    add("request", request)
    limits = request["resource_profile"]
    evidence = ingest_bytes(raw, source_kind=record["source_kind"],
                            track_source={"id": source["id"], "revision_id": source["revision_id"]},
                            max_source_bytes=max_source_bytes,
                            max_observations=limits["max_observations"],
                            max_parts=limits["max_parts"])
    _admit_ingestion(evidence)
    add("M2A", {"outcome": evidence.outcome, "result_json": _wire(evidence), "verification_json": None})
    policy = QualityPolicy(**request["quality_policy"])
    q = project_quality(evidence, policy=policy,
                        max_fragments=limits["max_quality_fragments"])
    qv = verify_quality(q.projection, evidence, policy=policy) if q.outcome == "produced" else None
    if qv is not None and qv.outcome != "valid":
        raise LocalEvidenceError("M3_QUALITY_VERIFICATION_FAILED")
    add("M2B", {"outcome": q.outcome, "result_json": _wire(q), "verification_json": _wire(qv) if qv else None})
    failure = None
    if q.outcome != "produced":
        failure = "M2B:" + q.outcome
    inputs = None
    if failure is None:
        area = request["target_area"]
        inputs = dict(evidence=evidence, quality_projection=q.projection, quality_policy=policy,
                      target_area=area, target_reference=ParentReference(area["id"], area["revision_id"]))
        c = prove_spatial_relation(**inputs)
        cv = verify_spatial_relation(c.proof, **inputs) if c.outcome == "produced" else None
        if cv is not None and cv.outcome != "valid":
            raise LocalEvidenceError("M3_SPATIAL_VERIFICATION_FAILED")
        add("M2C", {"outcome": c.outcome, "result_json": _wire(c), "verification_json": _wire(cv) if cv else None})
        if c.outcome != "produced":
            failure = "M2C:" + c.outcome
    if failure is None:
        d = assemble_spatial_entities(proof=c.proof, **inputs)
        dv = verify_spatial_entities(d.bundle, proof=c.proof, **inputs) if d.outcome in ("produced", "non_assessable") else None
        if dv is not None and dv.outcome != "valid":
            raise LocalEvidenceError("M3_ENTITY_VERIFICATION_FAILED")
        if d.bundle is not None:
            source_vertices = sum(len(part["observations"])
                                  for part in evidence.canonical_track["parts"])
            _output_vertices(d.bundle, limit=limits["max_output_vertices"],
                             initial=_target_vertices(area, limit=limits["max_target_vertices"]) + source_vertices)
        add("M2D", {"outcome": d.outcome, "result_json": _wire(d), "verification_json": _wire(dv) if dv else None})
        if d.outcome not in ("produced", "non_assessable"):
            failure = "M2D:" + d.outcome
    if failure is None:
        e = export_geojson(bundle=d.bundle, proof=c.proof, include_outside=request["include_outside"], **inputs)
        add("M2E", {"outcome": e.outcome, "result_json": _wire(e), "verification_json": None})
        if e.outcome != "produced":
            failure = "M2E:" + e.outcome
    if failure is None and request["temporal_mode"] is not None:
        f = export_temporal_geojson(bundle=d.bundle, proof=c.proof, include_outside=request["include_outside"],
                                   metric_mode=request["temporal_mode"], **inputs)
        add("M2F", {"outcome": f.outcome, "result_json": _wire(f), "verification_json": None})
        if f.outcome != "produced":
            failure = "M2F:" + f.outcome
    while len(nodes) < len(KINDS):
        kind = KINDS[len(nodes)]
        disabled = kind == "M2F" and failure is None and request["temporal_mode"] is None
        add(kind, {"outcome": "disabled" if disabled else "unavailable", "result_json": None,
                   "verification_json": None, "reason": "explicit_option" if disabled else failure})
    return {"encoding": ENCODING, "profile": "basic-local", "source":
            {"id": source["id"], "revision_id": source["revision_id"], "admission_digest": source_digest},
            "request": request, "request_digest": _sha(canonical_record(request)),
            "artifacts": artifacts, "algorithm_recipe": {
                "M2A": _recipe(record["source_kind"]),
                "M2B": loads_json(_wire(QualityAlgorithm(QualityParameters(policy)))),
                "M2C": loads_json(_wire(spatial_algorithm())),
                "M2D": {"name": M2D_NAME, "version": M2D_VERSION, "identity_policy": IDENTITY_POLICY, "snapshot_policy": SNAPSHOT_POLICY},
                "M2E": {"export_version": "m2e-geojson-v1", "include_outside": request["include_outside"],
                         "map_renderer": "render_geojson_map", "map_title": "Target area route map"},
                "M2F": {**TEMPORAL_ALGORITHM, "metric_mode": request["temporal_mode"]},
            }, "nodes": nodes, "outcome": "completed" if failure is None else "stage_unavailable"}


class LocalGraphStore(LocalEvidenceStore):
    def __init__(self, path, *, profile="basic-local"):
        super().__init__(path, profile=profile)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("PRAGMA user_version").fetchone()[0] == 1:
                db.execute("CREATE TABLE graphs (digest TEXT PRIMARY KEY, source_digest TEXT NOT NULL REFERENCES admissions(record_digest), request_digest TEXT NOT NULL, manifest BLOB NOT NULL)")
                db.execute("PRAGMA user_version=2")
                db.commit()

    @staticmethod
    def _commit(manifest, digest):
        return GraphCommit(digest, manifest["source"]["admission_digest"], manifest["request_digest"], manifest["outcome"])

    @staticmethod
    def _decode_graph(row):
        if row is None:
            raise LocalEvidenceError("M3_GRAPH_NOT_FOUND")
        digest, source_digest, request_digest, encoded = row
        try:
            if type(encoded) is not bytes or _sha(encoded) != digest:
                raise LocalEvidenceError("M3_GRAPH_CORRUPT")
            m = loads_json(encoded)
            if (type(m) is not dict or set(m) != {"encoding", "profile", "source", "request", "request_digest", "artifacts", "algorithm_recipe", "nodes", "outcome"}
                    or canonical_record(m) != encoded or m["encoding"] not in (ENCODING, LEGACY_ENCODING) or m["profile"] != "basic-local"
                    or m["source"]["admission_digest"] != source_digest or m["request_digest"] != request_digest
                    or _sha(canonical_record(m["request"])) != request_digest or len(m["nodes"]) != len(KINDS)):
                raise LocalEvidenceError("M3_GRAPH_CORRUPT")
            if (m["outcome"] not in ("completed", "stage_unavailable") or type(m["source"]) is not dict
                    or set(m["source"]) != {"id", "revision_id", "admission_digest"}
                    or any(type(v) is not str or not v for v in m["source"].values())
                    or type(m["algorithm_recipe"]) is not dict or set(m["algorithm_recipe"]) != set(KINDS[1:])):
                raise LocalEvidenceError("M3_GRAPH_CORRUPT")
            request_keys = {"target_area", "quality_policy", "include_outside", "temporal_mode"}
            if m["encoding"] == ENCODING:
                request_keys.add("resource_profile")
            if type(m["request"]) is not dict or set(m["request"]) != request_keys:
                raise LocalEvidenceError("M3_GRAPH_CORRUPT")
            seen = []
            for kind, node in zip(KINDS, m["nodes"]):
                if (type(node) is not dict or set(node) != {"kind", "parents", "payload_json", "sha256"}
                        or node["kind"] != kind or node["parents"] != [source_digest, *seen]
                        or _sha(canonical_record({k: node[k] for k in ("kind", "parents", "payload_json")})) != node["sha256"]):
                    raise LocalEvidenceError("M3_GRAPH_CORRUPT")
                payload = loads_json(node["payload_json"])
                if type(payload) is not dict:
                    raise LocalEvidenceError("M3_GRAPH_CORRUPT")
                if kind == "request":
                    if canonical_record(payload) != canonical_record(m["request"]):
                        raise LocalEvidenceError("M3_GRAPH_CORRUPT")
                elif (type(payload.get("outcome")) is not str
                      or not {"outcome", "result_json", "verification_json"} <= set(payload)
                      or any(payload[k] is not None and type(payload[k]) is not str for k in ("result_json", "verification_json"))):
                    raise LocalEvidenceError("M3_GRAPH_CORRUPT")
                else:
                    for key in ("result_json", "verification_json"):
                        if payload[key] is not None:
                            loads_json(payload[key])
                seen.append(node["sha256"])
            return m
        except (ValueError, TypeError, KeyError, RecursionError) as exc:
            if isinstance(exc, LocalEvidenceError):
                raise
            raise LocalEvidenceError("M3_GRAPH_CORRUPT") from exc

    def _graph(self, digest):
        if type(digest) is not str or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise LocalEvidenceError("M3_EXPECTED_GRAPH_INVALID")
        with self._connect() as db:
            row = db.execute("SELECT digest,source_digest,request_digest,CASE WHEN length(manifest)<=16777216 THEN manifest ELSE NULL END FROM graphs WHERE digest=?", (digest,)).fetchone()
        return self._decode_graph(row)

    def derive_graph(self, source_id, revision_id, *, expected_record_digest, target_area,
                     policy=QualityPolicy(), include_outside=True, temporal_mode="speed_mps",
                     max_source_bytes=None,
                     resource_profile=None):
        if resource_profile is None:
            if max_source_bytes is None:
                max_source_bytes = DEFAULT_TASK_RESOURCE_PROFILE.max_source_bytes
            resource_profile = replace(DEFAULT_TASK_RESOURCE_PROFILE,
                                       max_source_bytes=max_source_bytes)
        if type(resource_profile) is not TaskResourceProfile:
            raise LocalEvidenceError("M3_RESOURCE_PROFILE_INVALID")
        if max_source_bytes is None:
            max_source_bytes = resource_profile.max_source_bytes
        if type(max_source_bytes) is not int or max_source_bytes != resource_profile.max_source_bytes:
            raise LocalEvidenceError("M3_RESOURCE_PROFILE_INVALID")
        request = _request(target_area, policy, include_outside, temporal_mode, resource_profile)
        record, source_digest, raw = self._material(source_id, revision_id,
            expected_record_digest=expected_record_digest, max_source_bytes=max_source_bytes)
        try:
            artifacts = graph_artifacts()
        except (OSError, metadata.PackageNotFoundError) as exc:
            raise LocalEvidenceError("M3_ARTIFACT_UNAVAILABLE") from exc
        manifest = _pipeline(record, source_digest, raw, request, artifacts,
                             max_source_bytes=max_source_bytes)
        encoded = canonical_record(manifest)
        if len(encoded) > RECORD_BYTES_LIMIT:
            raise LocalEvidenceError("M3_GRAPH_LIMIT_EXCEEDED")
        digest = _sha(encoded)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            parent_row = db.execute("SELECT source_id,revision_id,record_digest,raw_digest,CASE WHEN length(record)<=16777216 THEN record ELSE NULL END FROM admissions WHERE source_id=? AND revision_id=?", (source_id, revision_id)).fetchone()
            parent = self._decode(parent_row)
            if parent_row[2] != source_digest:
                raise LocalEvidenceError("M3_EXPECTED_RECORD_MISMATCH")
            self._raw(db, parent, max_source_bytes)
            row = db.execute("SELECT digest,source_digest,request_digest,CASE WHEN length(manifest)<=16777216 THEN manifest ELSE NULL END FROM graphs WHERE digest=?", (digest,)).fetchone()
            if row is not None:
                existing = self._decode_graph(row)
                if canonical_record(existing) != encoded:
                    raise LocalEvidenceError("M3_GRAPH_CONFLICT")
            else:
                db.execute("INSERT INTO graphs VALUES (?,?,?,?)", (digest, source_digest, manifest["request_digest"], encoded))
                db.commit()
        return self._commit(manifest, digest)

    def graph_candidates(self, source_id, revision_id):
        if any(type(v) is not str or not v for v in (source_id, revision_id)):
            raise LocalEvidenceError("M3_SOURCE_REFERENCE_INVALID")
        with self._connect() as db:
            digests = db.execute("SELECT g.digest FROM graphs g JOIN admissions a ON a.record_digest=g.source_digest WHERE a.source_id=? AND a.revision_id=? ORDER BY g.digest", (source_id, revision_id)).fetchall()
        return tuple(self._commit(self._graph(row[0]), row[0]) for row in digests)

    def reload_graph(self, graph_digest, *, expected_source_digest, target_area,
                     policy=QualityPolicy(), include_outside=True, temporal_mode="speed_mps",
                     max_source_bytes=None,
                     resource_profile=None):
        if (type(expected_source_digest) is not str or len(expected_source_digest) != 64
                or any(c not in "0123456789abcdef" for c in expected_source_digest)):
            raise LocalEvidenceError("M3_EXPECTED_RECORD_INVALID")
        if resource_profile is None:
            if max_source_bytes is None:
                max_source_bytes = DEFAULT_TASK_RESOURCE_PROFILE.max_source_bytes
            resource_profile = replace(DEFAULT_TASK_RESOURCE_PROFILE,
                                       max_source_bytes=max_source_bytes)
        if type(resource_profile) is not TaskResourceProfile:
            raise LocalEvidenceError("M3_RESOURCE_PROFILE_INVALID")
        if max_source_bytes is None:
            max_source_bytes = resource_profile.max_source_bytes
        if type(max_source_bytes) is not int or max_source_bytes != resource_profile.max_source_bytes:
            raise LocalEvidenceError("M3_RESOURCE_PROFILE_INVALID")
        request = _request(target_area, policy, include_outside, temporal_mode, resource_profile)
        manifest = self._graph(graph_digest)
        if manifest["source"]["admission_digest"] != expected_source_digest:
            raise LocalEvidenceError("M3_GRAPH_SELECTOR_MISMATCH")
        if manifest["encoding"] == LEGACY_ENCODING:
            legacy_request = {k: v for k, v in request.items() if k != "resource_profile"}
            if canonical_record(legacy_request) != canonical_record(manifest["request"]):
                raise LocalEvidenceError("M3_GRAPH_SELECTOR_MISMATCH")
            return GraphReload("historical_unverified", self._commit(manifest, graph_digest), None,
                               ("legacy_graph_encoding",))
        if canonical_record(request) != canonical_record(manifest["request"]):
            raise LocalEvidenceError("M3_GRAPH_SELECTOR_MISMATCH")
        source = manifest["source"]
        record, _, raw = self._material(source["id"], source["revision_id"],
            expected_record_digest=expected_source_digest, max_source_bytes=max_source_bytes)
        commit = self._commit(manifest, graph_digest)
        try:
            artifacts = graph_artifacts()
        except (OSError, metadata.PackageNotFoundError):
            return GraphReload("historical_unverified", commit, None, ("artifact_unavailable",))
        if artifacts != manifest["artifacts"]:
            return GraphReload("historical_unverified", commit, None, ("artifact_digest_mismatch",))
        fresh = _pipeline(record, expected_source_digest, raw, request, artifacts,
                          max_source_bytes=max_source_bytes)
        if canonical_record(fresh) != canonical_record(manifest):
            raise LocalEvidenceError("M3_GRAPH_REPLAY_MISMATCH")
        return GraphReload("verified_local", commit, canonical_record(manifest).decode("utf-8"))
