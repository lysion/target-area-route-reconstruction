"""Basic-local human interpretation overlays; never mutate spatial evidence."""
from dataclasses import dataclass
from datetime import datetime

from .local_evidence import LocalEvidenceError, canonical_record, _sha
from .local_graph import LocalGraphStore
from .strict_json import loads_json

ENCODING = 'm3-local-review-v1'
REVIEW_BYTES_LIMIT = 65536
STREAM_LIMIT = 10000
FIELDS = {'encoding', 'decision_id', 'graph_digest', 'assessment', 'scope',
          'actor', 'reason', 'timestamp', 'action', 'relation', 'previous_digest'}


def _digest(value, *, optional=False):
    if optional and value is None:
        return
    if type(value) is not str or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise LocalEvidenceError('M3_REVIEW_INPUT_INVALID')


def _validate(record):
    if type(record) is not dict or set(record) != FIELDS or record['encoding'] != ENCODING:
        raise LocalEvidenceError('M3_REVIEW_INPUT_INVALID')
    for key in ('decision_id', 'scope', 'actor', 'reason', 'timestamp'):
        if type(record[key]) is not str or not record[key].strip():
            raise LocalEvidenceError('M3_REVIEW_INPUT_INVALID')
    _digest(record['graph_digest'])
    _digest(record['previous_digest'], optional=True)
    ref = record['assessment']
    if type(ref) is not dict or set(ref) != {'id', 'revision_id'} or any(type(v) is not str or not v for v in ref.values()):
        raise LocalEvidenceError('M3_REVIEW_INPUT_INVALID')
    try:
        stamp = record['timestamp']
        parsed = datetime.strptime(stamp, '%Y-%m-%dT%H:%M:%S.%fZ')
        if parsed.isoformat(timespec='microseconds') + 'Z' != stamp:
            raise ValueError('noncanonical timestamp')
    except ValueError as exc:
        raise LocalEvidenceError('M3_REVIEW_INPUT_INVALID') from exc
    action, relation = record['action'], record['relation']
    if (type(action) is not str or action not in ('set', 'revoke')
            or (action == 'set' and (type(relation) is not str or relation not in ('inside', 'outside', 'partial', 'unknown')))
            or (action == 'revoke' and relation is not None)):
        raise LocalEvidenceError('M3_REVIEW_INPUT_INVALID')


@dataclass(frozen=True)
class ManualDecision:
    decision_id: str
    digest: str
    record_json: str


@dataclass(frozen=True)
class EffectiveReview:
    graph_digest: str
    assessment_json: str
    scope: str
    head_digest: str | None
    algorithmic_relation: str
    effective_relation: str
    audit_json: str
    status: str = 'verified_local'
    verification_scope: str = 'manual-task-projection'


class LocalReviewStore(LocalGraphStore):
    """Explicit opt-in schema migration and serial append-only review streams."""
    def __init__(self, path, *, profile='basic-local'):
        super().__init__(path, profile=profile)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('PRAGMA user_version').fetchone()[0] == 2:
                db.execute('CREATE TABLE reviews (sequence INTEGER PRIMARY KEY, decision_id TEXT NOT NULL UNIQUE, digest TEXT NOT NULL UNIQUE, graph_digest TEXT NOT NULL REFERENCES graphs(digest), scope TEXT NOT NULL, record BLOB NOT NULL)')
                db.execute('CREATE INDEX review_stream ON reviews(graph_digest,scope,sequence)')
                db.execute('PRAGMA user_version=3')
                db.commit()

    def _assessment(self, graph_digest, selectors):
        replay = self.reload_graph(graph_digest, **selectors)
        if replay.status != 'verified_local':
            raise LocalEvidenceError('M3_REVIEW_GRAPH_UNVERIFIED')
        manifest = loads_json(replay.manifest_json)
        stage = loads_json(manifest['nodes'][4]['payload_json'])
        result = loads_json(stage['result_json']) if stage['result_json'] else None
        if result is None or result.get('bundle') is None:
            raise LocalEvidenceError('M3_REVIEW_ASSESSMENT_UNAVAILABLE')
        return result['bundle']['assessment_json']

    @staticmethod
    def _scope(scope, expected_head):
        if type(scope) is not str or not scope.strip():
            raise LocalEvidenceError('M3_REVIEW_INPUT_INVALID')
        _digest(expected_head, optional=True)

    @staticmethod
    def _history(db, graph_digest, scope, assessment):
        rows = db.execute('SELECT decision_id,digest,CASE WHEN length(record)<=65536 THEN record ELSE NULL END FROM reviews WHERE graph_digest=? AND scope=? ORDER BY sequence LIMIT ?', (graph_digest, scope, STREAM_LIMIT + 1)).fetchall()
        if len(rows) > STREAM_LIMIT:
            raise LocalEvidenceError('M3_REVIEW_LIMIT_EXCEEDED')
        history = []
        previous = None
        for decision_id, digest, encoded in rows:
            try:
                if type(encoded) is not bytes or _sha(encoded) != digest:
                    raise ValueError('digest')
                record = loads_json(encoded)
                _validate(record)
                if (canonical_record(record) != encoded or record['decision_id'] != decision_id
                        or record['graph_digest'] != graph_digest or record['scope'] != scope
                        or record['assessment'] != assessment or record['previous_digest'] != previous
                        or (record['action'] == 'revoke' and (not history or history[-1]['action'] != 'set'))):
                    raise ValueError('chain')
            except (ValueError, TypeError, KeyError, RecursionError) as exc:
                raise LocalEvidenceError('M3_REVIEW_CORRUPT') from exc
            history.append(record)
            previous = digest
        return history, previous

    def append_decision(self, graph_digest, *, scope, expected_head, decision_id,
                        actor, reason, timestamp, action='set', relation=None, **selectors):
        self._scope(scope, expected_head)
        # Reject non-native input before replay, hashing or persistence.
        record = dict(encoding=ENCODING, decision_id=decision_id, graph_digest=graph_digest,
                      assessment={'id': 'pending', 'revision_id': 'pending'}, scope=scope,
                      actor=actor, reason=reason, timestamp=timestamp, action=action,
                      relation=relation, previous_digest=expected_head)
        _validate(record)
        if len(canonical_record(record)) > REVIEW_BYTES_LIMIT:
            raise LocalEvidenceError('M3_REVIEW_LIMIT_EXCEEDED')
        assessment_json = self._assessment(graph_digest, selectors)
        assessment = loads_json(assessment_json)
        ref = {k: assessment[k] for k in ('id', 'revision_id')}
        record['assessment'] = ref
        encoded = canonical_record(record)
        if len(encoded) > REVIEW_BYTES_LIMIT:
            raise LocalEvidenceError('M3_REVIEW_LIMIT_EXCEEDED')
        digest = _sha(encoded)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            history, head = self._history(db, graph_digest, scope, ref)
            old = db.execute('SELECT digest,CASE WHEN length(record)<=65536 THEN record ELSE NULL END FROM reviews WHERE decision_id=?', (decision_id,)).fetchone()
            if old is not None:
                if old != (digest, encoded) or record not in history:
                    raise LocalEvidenceError('M3_REVIEW_ID_CONFLICT')
            else:
                if head != expected_head:
                    raise LocalEvidenceError('M3_REVIEW_HEAD_CONFLICT')
                if action == 'revoke' and (not history or history[-1]['action'] != 'set'):
                    raise LocalEvidenceError('M3_REVIEW_NOT_ACTIVE')
                if len(history) >= STREAM_LIMIT:
                    raise LocalEvidenceError('M3_REVIEW_LIMIT_EXCEEDED')
                db.execute('INSERT INTO reviews(decision_id,digest,graph_digest,scope,record) VALUES (?,?,?,?,?)', (decision_id, digest, graph_digest, scope, encoded))
                db.commit()
        return ManualDecision(decision_id, digest, encoded.decode('utf-8'))

    def effective_review(self, graph_digest, *, scope, expected_head, **selectors):
        self._scope(scope, expected_head)
        assessment_json = self._assessment(graph_digest, selectors)
        assessment = loads_json(assessment_json)
        ref = {k: assessment[k] for k in ('id', 'revision_id')}
        with self._connect() as db:
            history, head = self._history(db, graph_digest, scope, ref)
        if head != expected_head:
            raise LocalEvidenceError('M3_REVIEW_HEAD_CONFLICT')
        relation = assessment['relation']
        effective = history[-1]['relation'] if history and history[-1]['action'] == 'set' else relation
        return EffectiveReview(graph_digest, assessment_json, scope,
                               head, relation, effective, canonical_record(history).decode('utf-8'))
