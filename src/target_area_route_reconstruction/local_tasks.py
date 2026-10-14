"""Caller-driven local task attempts; durable metadata is never cached authority."""
from dataclasses import dataclass
from importlib import metadata

from .ingestion import DEFAULT_SOURCE_BYTES, MAX_SOURCE_BYTES
from .local_evidence import LocalEvidenceError, canonical_record, _sha
from .local_graph import _request, graph_artifacts
from .local_review import LocalReviewStore
from .quality_models import QualityPolicy
from .strict_json import loads_json

ENCODING = 'm3-local-task-v1'
EVENT_ENCODING = 'm3-local-task-event-v1'
EVENT_LIMIT = 1000


def _hex(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _text(value):
    if type(value) is not str or not value.strip() or len(value.encode('utf-8', errors='replace')) > 4096:
        raise LocalEvidenceError('M3_TASK_INPUT_INVALID')
    canonical_record(value)  # Reject unpaired Unicode before SQLite.


def _artifacts():
    try:
        return _sha(canonical_record(graph_artifacts()))
    except (OSError, metadata.PackageNotFoundError) as exc:
        raise LocalEvidenceError('M3_ARTIFACT_UNAVAILABLE') from exc


@dataclass(frozen=True)
class TaskSnapshot:
    task_id: str
    request_digest: str
    head_digest: str
    state: str
    graph_digest: str | None
    failure_code: str | None
    verification_scope: str = 'task-lifecycle-only'


class LocalTaskStore(LocalReviewStore):
    def __init__(self, path, *, profile='basic-local'):
        super().__init__(path, profile=profile)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('PRAGMA user_version').fetchone()[0] == 3:
                db.execute('CREATE TABLE tasks (task_id TEXT PRIMARY KEY, request_digest TEXT NOT NULL, source_digest TEXT NOT NULL REFERENCES admissions(record_digest), request BLOB NOT NULL)')
                db.execute('CREATE TABLE task_events (sequence INTEGER PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id), digest TEXT NOT NULL UNIQUE, record BLOB NOT NULL)')
                db.execute('CREATE INDEX task_journal ON task_events(task_id,sequence)')
                db.execute('PRAGMA user_version=4')
                db.commit()

    @staticmethod
    def _selectors(request):
        r = request['graph_request']
        return dict(expected_source_digest=request['source']['admission_digest'], target_area=r['target_area'],
                    policy=QualityPolicy(**r['quality_policy']), include_outside=r['include_outside'],
                    temporal_mode=r['temporal_mode'], max_source_bytes=request['max_source_bytes'])

    @staticmethod
    def _load(db, task_id, expected_request_digest):
        _text(task_id)
        if not _hex(expected_request_digest):
            raise LocalEvidenceError('M3_TASK_INPUT_INVALID')
        row = db.execute('SELECT request_digest,source_digest,CASE WHEN length(request)<=16777216 THEN request ELSE NULL END FROM tasks WHERE task_id=?', (task_id,)).fetchone()
        if row is None:
            raise LocalEvidenceError('M3_TASK_NOT_FOUND')
        digest, source_digest, encoded = row
        if digest != expected_request_digest:
            raise LocalEvidenceError('M3_TASK_REQUEST_MISMATCH')
        try:
            if type(encoded) is not bytes or _sha(encoded) != digest:
                raise ValueError('hash')
            r = loads_json(encoded)
            if (type(r) is not dict or set(r) != {'encoding','profile','task_id','source','graph_request','artifacts_digest','expected_graph_digest','max_source_bytes'}
                    or canonical_record(r) != encoded or r['encoding'] != ENCODING or r['profile'] != 'basic-local'
                    or r['task_id'] != task_id or type(r['source']) is not dict or set(r['source']) != {'id','revision_id','admission_digest'}
                    or r['source']['admission_digest'] != source_digest or not _hex(source_digest)
                    or not _hex(r['artifacts_digest']) or (r['expected_graph_digest'] is not None and not _hex(r['expected_graph_digest']))
                    or type(r['max_source_bytes']) is not int or not 1 <= r['max_source_bytes'] <= MAX_SOURCE_BYTES):
                raise ValueError('request')
            for key in ('id', 'revision_id'):
                _text(r['source'][key])
            g = r['graph_request']
            if type(g) is not dict or set(g) != {'target_area','quality_policy','include_outside','temporal_mode'}:
                raise ValueError('graph request')
            if canonical_record(_request(g['target_area'], QualityPolicy(**g['quality_policy']), g['include_outside'], g['temporal_mode'])) != canonical_record(g):
                raise ValueError('graph request')
            return r
        except (ValueError, TypeError, KeyError, RecursionError) as exc:
            raise LocalEvidenceError('M3_TASK_CORRUPT') from exc

    @staticmethod
    def _events(db, task_id, request_digest):
        rows = db.execute('SELECT digest,CASE WHEN length(record)<=65536 THEN record ELSE NULL END FROM task_events WHERE task_id=? ORDER BY sequence LIMIT ?', (task_id, EVENT_LIMIT + 1)).fetchall()
        if not rows or len(rows) > EVENT_LIMIT:
            raise LocalEvidenceError('M3_TASK_CORRUPT')
        previous = None
        state = None
        history = []
        for digest, encoded in rows:
            try:
                if type(encoded) is not bytes or _sha(encoded) != digest:
                    raise ValueError('hash')
                e = loads_json(encoded)
                if (type(e) is not dict or set(e) != {'encoding','task_id','request_digest','previous_digest','state','actor','graph_digest','failure_code'}
                        or canonical_record(e) != encoded or e['encoding'] != EVENT_ENCODING or e['task_id'] != task_id
                        or e['request_digest'] != request_digest or e['previous_digest'] != previous):
                    raise ValueError('event')
                _text(e['actor'])
                if e['state'] not in {None: ('queued',), 'queued': ('running',), 'running': ('completed','failed'), 'failed': ('running',), 'completed': ()}[state]:
                    raise ValueError('transition')
                if e['state'] == 'completed':
                    if not _hex(e['graph_digest']) or e['failure_code'] is not None:
                        raise ValueError('completion')
                elif e['graph_digest'] is not None:
                    raise ValueError('graph')
                if e['state'] == 'failed':
                    _text(e['failure_code'])
                elif e['failure_code'] is not None:
                    raise ValueError('failure')
                previous, state = digest, e['state']
                history.append(e)
            except (ValueError, TypeError, KeyError, RecursionError) as exc:
                raise LocalEvidenceError('M3_TASK_CORRUPT') from exc
        return TaskSnapshot(task_id, request_digest, previous, state, e['graph_digest'], e['failure_code']), tuple(history)

    @staticmethod
    def _append(db, task_id, request_digest, previous, state, actor, graph=None, failure=None):
        e = dict(encoding=EVENT_ENCODING, task_id=task_id, request_digest=request_digest,
                 previous_digest=previous, state=state, actor=actor, graph_digest=graph, failure_code=failure)
        encoded = canonical_record(e)
        if len(encoded) > 65536:
            raise LocalEvidenceError('M3_TASK_LIMIT_EXCEEDED')
        digest = _sha(encoded)
        db.execute('INSERT INTO task_events(task_id,digest,record) VALUES (?,?,?)', (task_id,digest,encoded))
        db.commit()
        return TaskSnapshot(task_id, request_digest, digest, state, graph, failure)

    def submit_task(self, task_id, source_id, revision_id, *, actor, expected_record_digest,
                    target_area, policy=QualityPolicy(), include_outside=True, temporal_mode='speed_mps',
                    expected_graph_digest=None, max_source_bytes=DEFAULT_SOURCE_BYTES):
        for value in (task_id, source_id, revision_id, actor): _text(value)
        if (not _hex(expected_record_digest) or (expected_graph_digest is not None and not _hex(expected_graph_digest))
                or type(max_source_bytes) is not int or not 1 <= max_source_bytes <= MAX_SOURCE_BYTES):
            raise LocalEvidenceError('M3_TASK_INPUT_INVALID')
        graph_request = _request(target_area, policy, include_outside, temporal_mode)
        self._material(source_id, revision_id, expected_record_digest=expected_record_digest, max_source_bytes=max_source_bytes)
        r = dict(encoding=ENCODING, profile='basic-local', task_id=task_id,
                 source=dict(id=source_id, revision_id=revision_id, admission_digest=expected_record_digest),
                 graph_request=graph_request, artifacts_digest=_artifacts(), expected_graph_digest=expected_graph_digest,
                 max_source_bytes=max_source_bytes)
        encoded = canonical_record(r)
        if len(encoded) > 16777216:
            raise LocalEvidenceError('M3_TASK_LIMIT_EXCEEDED')
        digest = _sha(encoded)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT request_digest FROM tasks WHERE task_id=?', (task_id,)).fetchone()
            if old is not None:
                if old[0] != digest:
                    raise LocalEvidenceError('M3_TASK_ID_CONFLICT')
                self._load(db, task_id, digest)
                return self._events(db, task_id, digest)[0]
            db.execute('INSERT INTO tasks VALUES (?,?,?,?)', (task_id,digest,expected_record_digest,encoded))
            return self._append(db, task_id, digest, None, 'queued', actor)

    def task_snapshot(self, task_id, *, expected_request_digest):
        with self._connect() as db:
            db.execute('BEGIN')
            self._load(db, task_id, expected_request_digest)
            return self._events(db, task_id, expected_request_digest)[0]

    def task_history(self, task_id, *, expected_request_digest, expected_head):
        if not _hex(expected_head):
            raise LocalEvidenceError('M3_TASK_INPUT_INVALID')
        with self._connect() as db:
            db.execute('BEGIN')
            self._load(db, task_id, expected_request_digest)
            state, history = self._events(db, task_id, expected_request_digest)
        if state.head_digest != expected_head:
            raise LocalEvidenceError('M3_TASK_HEAD_CONFLICT')
        return canonical_record(list(history)).decode('utf-8')

    def _transition(self, task_id, request_digest, head, actor, state, *, graph=None, failure=None):
        _text(actor)
        if not _hex(head):
            raise LocalEvidenceError('M3_TASK_INPUT_INVALID')
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            request = self._load(db, task_id, request_digest)
            old, history = self._events(db, task_id, request_digest)
            count = len(history)
            if old.head_digest != head:
                raise LocalEvidenceError('M3_TASK_HEAD_CONFLICT')
            allowed = ('queued','failed') if state == 'running' else ('running',)
            if old.state not in allowed:
                raise LocalEvidenceError('M3_TASK_STATE_CONFLICT')
            if count + (2 if state == 'running' else 1) > EVENT_LIMIT:
                raise LocalEvidenceError('M3_TASK_LIMIT_EXCEEDED')
            return request, self._append(db, task_id, request_digest, head, state, actor, graph, failure)

    def recover_task(self, task_id, *, expected_request_digest, expected_head, actor):
        return self._transition(task_id, expected_request_digest, expected_head, actor, 'failed', failure='M3_TASK_INTERRUPTED')[1]

    def task_result(self, task_id, *, expected_request_digest, expected_head):
        if not _hex(expected_head):
            raise LocalEvidenceError('M3_TASK_INPUT_INVALID')
        with self._connect() as db:
            db.execute('BEGIN')
            request = self._load(db, task_id, expected_request_digest)
            state, _ = self._events(db, task_id, expected_request_digest)
        if state.head_digest != expected_head:
            raise LocalEvidenceError('M3_TASK_HEAD_CONFLICT')
        if state.state != 'completed':
            raise LocalEvidenceError('M3_TASK_RESULT_UNAVAILABLE')
        if _artifacts() != request['artifacts_digest']:
            raise LocalEvidenceError('M3_TASK_ARTIFACT_MISMATCH')
        if request['expected_graph_digest'] is not None and state.graph_digest != request['expected_graph_digest']:
            raise LocalEvidenceError('M3_TASK_CORRUPT')
        return self._replay(request, state.graph_digest)

    def _replay(self, request, graph):
        result = self.reload_graph(graph, **self._selectors(request))
        if result.status != 'verified_local':
            raise LocalEvidenceError('M3_TASK_GRAPH_UNVERIFIED')
        manifest = loads_json(result.manifest_json)
        if (manifest['source'] != request['source']
                or _sha(canonical_record(manifest['artifacts'])) != request['artifacts_digest']):
            raise LocalEvidenceError('M3_TASK_GRAPH_UNVERIFIED')
        return result

    def run_task(self, task_id, *, expected_request_digest, expected_head, actor):
        _text(actor)
        if not _hex(expected_head):
            raise LocalEvidenceError('M3_TASK_INPUT_INVALID')
        old = self.task_snapshot(task_id, expected_request_digest=expected_request_digest)
        if old.head_digest != expected_head:
            raise LocalEvidenceError('M3_TASK_HEAD_CONFLICT')
        if old.state == 'completed':
            self.task_result(task_id, expected_request_digest=expected_request_digest, expected_head=expected_head)
            return old
        request, claim = self._transition(task_id, expected_request_digest, expected_head, actor, 'running')
        try:
            if _artifacts() != request['artifacts_digest']:
                raise LocalEvidenceError('M3_TASK_ARTIFACT_MISMATCH')
            selectors = self._selectors(request)
            graph = request['expected_graph_digest']
            if graph is None:
                args = dict(selectors)
                args['expected_record_digest'] = args.pop('expected_source_digest')
                graph = self.derive_graph(request['source']['id'], request['source']['revision_id'], **args).graph_digest
            self._replay(request, graph)
        except Exception as exc:
            code = exc.code if isinstance(exc, LocalEvidenceError) else 'M3_TASK_EXECUTION_FAILED'
            failed = self._transition(task_id, expected_request_digest, claim.head_digest, actor, 'failed', failure=code)[1]
            if not isinstance(exc, LocalEvidenceError):
                raise
            return failed
        return self._transition(task_id, expected_request_digest, claim.head_digest, actor, 'completed', graph=graph)[1]
