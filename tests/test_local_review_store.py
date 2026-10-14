"""Manual overlays: independent lifecycle, strict input, cold replay and crashes."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from target_area_route_reconstruction import LocalGraphStore, LocalReviewStore, LocalEvidenceError

FIXTURES = Path(os.environ.get('M3_SOURCE_FIXTURES', Path(__file__).resolve().parent / 'source-fixtures'))
SOURCE = {'schema_version': '0.1.0', 'id': 's', 'revision_id': 'r', 'activity': {'id': 'a'},
          'origin': {'namespace': 'local'}, 'representation': {'media_type': 'application/gpx+xml'}}
AREA = {'schema_version': '0.1.0', 'id': 't', 'revision_id': 'r', 'spatial_reference': 'OGC:CRS84',
        'geometry': {'type': 'Polygon', 'coordinates': [[[112.902,28.19],[112.908,28.19],[112.908,28.22],[112.902,28.22],[112.902,28.19]]]},
        'definition_provenance': {'description': 'Review test'}}


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'review.db'
        # Explicit v2→v3 migration must preserve old rows byte-for-byte.
        old = LocalGraphStore(self.path)
        a = old.admit_file(FIXTURES / 'equivalent/basic.gpx', source_kind='gpx', track_source=SOURCE)
        self.selectors = dict(expected_source_digest=a.record_digest, target_area=AREA)
        self.graph = old.derive_graph('s', 'r', expected_record_digest=a.record_digest, target_area=AREA)
        with sqlite3.connect(self.path) as db:
            self.before = db.execute('SELECT manifest FROM graphs').fetchone()[0]
        self.store = LocalReviewStore(self.path)
        self.arguments = dict(scope='task-A', expected_head=None, decision_id='review-1', actor='reviewer',
                              reason='Task interpretation', timestamp='2026-10-14T12:00:00.000000Z', relation='outside')

    def append(self, **changes):
        return self.store.append_decision(self.graph.graph_digest, **(self.arguments | changes), **self.selectors)

    def effective(self, head=None, scope='task-A'):
        return self.store.effective_review(self.graph.graph_digest, scope=scope, expected_head=head, **self.selectors)

    def test_overlay_correction_revocation_preserves_evidence(self):
        self.assertEqual(self.effective().effective_relation, 'partial')
        first = self.append(); self.assertEqual(first, self.append())
        result = self.effective(first.digest)
        self.assertEqual((result.algorithmic_relation, result.effective_relation), ('partial', 'outside'))
        second = self.append(decision_id='review-2', expected_head=first.digest, relation='inside')
        self.assertEqual(self.effective(second.digest).effective_relation, 'inside')
        third = self.append(decision_id='review-3', expected_head=second.digest, action='revoke', relation=None)
        result = self.effective(third.digest)
        self.assertEqual(result.effective_relation, 'partial')
        self.assertEqual(len(json.loads(result.audit_json)), 3)
        self.assertEqual(first, self.append()) # exact retry after later decisions
        fourth = self.append(decision_id='review-4', expected_head=third.digest, relation='unknown')
        self.assertEqual(self.effective(fourth.digest).effective_relation, 'unknown')
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT manifest FROM graphs').fetchone()[0], self.before)
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 3)
        self.assertEqual(LocalGraphStore(self.path).reload_graph(self.graph.graph_digest, **self.selectors).status, 'verified_local')

    def test_scope_head_identity_and_revocation_conflicts(self):
        with self.assertRaisesRegex(LocalEvidenceError, 'M3_REVIEW_NOT_ACTIVE'):
            self.append(action='revoke', relation=None)
        first = self.append()
        for changes, code in ((dict(reason='changed'), 'ID_CONFLICT'), (dict(decision_id='other'), 'HEAD_CONFLICT')):
            with self.assertRaisesRegex(LocalEvidenceError, 'M3_REVIEW_' + code): self.append(**changes)
        with self.assertRaisesRegex(LocalEvidenceError, 'M3_REVIEW_HEAD_CONFLICT'): self.effective()
        self.assertEqual(self.effective(scope='task-B').effective_relation, 'partial')
        self.append(scope='task-B', decision_id='other-scope', relation='inside')
        self.assertEqual(self.effective(first.digest).effective_relation, 'outside')
        revoked = self.append(decision_id='revoke', expected_head=first.digest, action='revoke', relation=None)
        with self.assertRaisesRegex(LocalEvidenceError, 'M3_REVIEW_NOT_ACTIVE'):
            self.append(decision_id='again', expected_head=revoked.digest, action='revoke', relation=None)

    def test_noncanonical_types_refused_before_replay(self):
        from dataclasses import dataclass
        @dataclass
        class Foreign:
            value: str = 'outside'
        class Text(str): pass
        for field in ('scope', 'expected_head', 'decision_id', 'actor', 'reason', 'timestamp', 'action', 'relation'):
            for value in (False, 0, 0.0, -0.0, Foreign(), Text('outside')):
                with self.subTest(field=field, value=value), patch.object(self.store, 'reload_graph') as reload:
                    with self.assertRaisesRegex(LocalEvidenceError, 'M3_REVIEW_INPUT_INVALID'):
                        self.append(**{field: value})
                    reload.assert_not_called()
        for stamp in ('2026-10-14T12:00:00Z', '2026-02-30T12:00:00.000000Z', '2026-10-14T12:00:00.000000+00:00'):
            with self.assertRaisesRegex(LocalEvidenceError, 'M3_REVIEW_INPUT_INVALID'): self.append(timestamp=stamp)
        with patch.object(self.store, 'reload_graph') as reload:
            with self.assertRaisesRegex(LocalEvidenceError, 'M3_REVIEW_LIMIT_EXCEEDED'): self.append(reason='x' * 65536)
            reload.assert_not_called()

    def test_tampering_and_missing_history_refused(self):
        first = self.append()
        second = self.append(decision_id='second', expected_head=first.digest)
        with sqlite3.connect(self.path) as db: db.execute('DELETE FROM reviews WHERE decision_id=?', ('review-1',))
        with self.assertRaisesRegex(LocalEvidenceError, 'M3_REVIEW_CORRUPT'): self.effective(second.digest)
        with sqlite3.connect(self.path) as db: db.execute('DELETE FROM reviews')
        with self.assertRaisesRegex(LocalEvidenceError, 'M3_REVIEW_HEAD_CONFLICT'): self.effective(second.digest)
        first = self.append()
        with sqlite3.connect(self.path) as db: db.execute('UPDATE reviews SET record=?', (b'x' * 65537,))
        with self.assertRaisesRegex(LocalEvidenceError, 'M3_REVIEW_CORRUPT'): self.effective(first.digest)

    def test_rehashed_invalid_stored_records_are_not_accepted(self):
        import hashlib
        first = self.append()
        original = json.loads(first.record_json)
        mutations = [original | {'relation': False}, original | {'extra': 0},
                     original | {'assessment': {'id': 'wrong', 'revision_id': 'wrong'}}]
        encoded_cases = [json.dumps(m, sort_keys=True, separators=(',', ':')).encode() for m in mutations]
        encoded_cases.append(first.record_json.replace('"action":"set"', '"action":"set","action":"set"').encode())
        for encoded in encoded_cases:
            digest = hashlib.sha256(encoded).hexdigest()
            with sqlite3.connect(self.path) as db:
                db.execute('UPDATE reviews SET digest=?,record=?', (digest, encoded))
            with self.assertRaisesRegex(LocalEvidenceError, 'M3_REVIEW_CORRUPT'):
                self.effective(digest)

    def test_unavailable_graph_and_wrong_selectors_do_not_publish(self):
        with patch('target_area_route_reconstruction.local_graph.graph_artifacts', side_effect=OSError('missing')):
            with self.assertRaisesRegex(LocalEvidenceError, 'M3_REVIEW_GRAPH_UNVERIFIED'): self.append()
            with self.assertRaisesRegex(LocalEvidenceError, 'M3_REVIEW_GRAPH_UNVERIFIED'): self.effective()
        self.selectors['include_outside'] = False
        with self.assertRaisesRegex(LocalEvidenceError, 'M3_GRAPH_SELECTOR_MISMATCH'): self.append()
        with sqlite3.connect(self.path) as db: self.assertEqual(db.execute('SELECT count(*) FROM reviews').fetchone()[0], 0)

    def test_no_assessment_refused_and_graphs_do_not_inherit_review(self):
        first = self.append()
        raw = b'<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="negative"/>'
        negative_source = SOURCE | {'id': 'negative'}
        a = self.store.admit_bytes(raw, source_kind='gpx', track_source=negative_source)
        graph = self.store.derive_graph('negative', 'r', expected_record_digest=a.record_digest, target_area=AREA)
        with self.assertRaisesRegex(LocalEvidenceError, 'M3_REVIEW_ASSESSMENT_UNAVAILABLE'):
            self.store.append_decision(graph.graph_digest, **self.arguments,
                expected_source_digest=a.record_digest, target_area=AREA)
        other_area = AREA | {'revision_id': 'r2'}
        other = self.store.derive_graph('s', 'r', expected_record_digest=self.selectors['expected_source_digest'], target_area=other_area)
        result = self.store.effective_review(other.graph_digest, scope='task-A', expected_head=None,
            expected_source_digest=self.selectors['expected_source_digest'], target_area=other_area)
        self.assertEqual(result.effective_relation, 'partial')
        self.assertEqual(result.audit_json, '[]')
        self.assertEqual(self.effective(first.digest).effective_relation, 'outside')
        # Preserve the exact M2 assessment JSON, including its numeric representation.
        m = json.loads(self.before)
        assessment_json = json.loads(json.loads(m['nodes'][4]['payload_json'])['result_json'])['bundle']['assessment_json']
        self.assertEqual(self.effective(first.digest).assessment_json, assessment_json)

    def test_stream_limit_is_atomic_and_retry_still_works(self):
        first = self.append()
        with patch('target_area_route_reconstruction.local_review.STREAM_LIMIT', 1):
            self.assertEqual(first, self.append())
            with self.assertRaisesRegex(LocalEvidenceError, 'M3_REVIEW_LIMIT_EXCEEDED'):
                self.append(decision_id='second', expected_head=first.digest)
        self.assertEqual(len(json.loads(self.effective(first.digest).audit_json)), 1)

    def test_separate_process_read_and_competing_corrections(self):
        first = self.append()
        script = '''import json,sys
from target_area_route_reconstruction import LocalReviewStore,LocalEvidenceError
s=LocalReviewStore(sys.argv[1]);args=json.loads(sys.argv[3]);selectors=json.loads(sys.argv[4])
try:
 r=s.append_decision(sys.argv[2],**args,**selectors);print(r.digest)
except LocalEvidenceError as e:print(e.code)
'''
        children = []
        for i in range(2):
            args = self.arguments | dict(decision_id=f'correction-{i}', expected_head=first.digest, relation='inside')
            children.append(subprocess.Popen([sys.executable, '-c', script, str(self.path), self.graph.graph_digest, json.dumps(args), json.dumps(self.selectors)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        outputs = []
        for child in children:
            out, err = child.communicate(timeout=60); self.assertEqual(child.returncode, 0, err); outputs.append(out.strip())
        self.assertEqual(outputs.count('M3_REVIEW_HEAD_CONFLICT'), 1)
        head = next(o for o in outputs if o != 'M3_REVIEW_HEAD_CONFLICT')
        code = 'import json,sys;from target_area_route_reconstruction import LocalReviewStore;r=LocalReviewStore(sys.argv[1]).effective_review(sys.argv[2],scope="task-A",expected_head=sys.argv[3],**json.loads(sys.argv[4]));assert r.algorithmic_relation=="partial" and r.effective_relation=="inside";print(r.status)'
        run = subprocess.run([sys.executable, '-c', code, str(self.path), self.graph.graph_digest, head, json.dumps(self.selectors)], capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr); self.assertEqual(run.stdout.strip(), 'verified_local')

    def test_process_crash_before_and_after_append_commit(self):
        script = '''import json,os,sqlite3,sys
from target_area_route_reconstruction import LocalReviewStore
s=LocalReviewStore(sys.argv[1]);original=sqlite3.connect
class C(sqlite3.Connection):
 def commit(self):
  if sys.argv[5]=="before":os._exit(77)
  super().commit();os._exit(78)
def connect(*a,**k):return original(*a,**k,factory=C)
sqlite3.connect=connect
s.append_decision(sys.argv[2],**json.loads(sys.argv[3]),**json.loads(sys.argv[4]))
'''
        for when, count in (('before', 0), ('after', 1)):
            run = subprocess.run([sys.executable, '-c', script, str(self.path), self.graph.graph_digest, json.dumps(self.arguments), json.dumps(self.selectors), when], capture_output=True, text=True, timeout=60)
            self.assertEqual(run.returncode, 77 if when == 'before' else 78, run.stderr)
            with sqlite3.connect(self.path) as db: self.assertEqual(db.execute('SELECT count(*) FROM reviews').fetchone()[0], count)
        self.assertEqual(self.effective(self.append().digest).effective_relation, 'outside')


if __name__ == '__main__': unittest.main()
