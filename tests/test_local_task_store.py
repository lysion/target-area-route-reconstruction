"""Task metadata cannot substitute for verified evidence; real restart/fencing tests."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from target_area_route_reconstruction import LocalTaskStore, LocalEvidenceError

FIXTURES = Path(os.environ.get('M3_SOURCE_FIXTURES', Path(__file__).resolve().parent / 'source-fixtures'))
SOURCE = {'schema_version':'0.1.0','id':'s','revision_id':'r','activity':{'id':'a'},'origin':{'namespace':'local'},'representation':{'media_type':'application/gpx+xml'}}
AREA = {'schema_version':'0.1.0','id':'t','revision_id':'r','spatial_reference':'OGC:CRS84',
        'geometry':{'type':'Polygon','coordinates':[[[112.902,28.19],[112.908,28.19],[112.908,28.22],[112.902,28.22],[112.902,28.19]]]},
        'definition_provenance':{'description':'Task test'}}


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'task.db'; self.store = LocalTaskStore(self.path)
        self.a = self.store.admit_file(FIXTURES/'equivalent/basic.gpx',source_kind='gpx',track_source=SOURCE)

    def submit(self, task_id='task', **options):
        return self.store.submit_task(task_id,'s','r',actor='submitter',expected_record_digest=self.a.record_digest,target_area=options.pop('target_area',AREA),**options)

    def run_task(self, task):
        return self.store.run_task(task.task_id,expected_request_digest=task.request_digest,expected_head=task.head_digest,actor='worker')

    def result(self, task):
        return self.store.task_result(task.task_id,expected_request_digest=task.request_digest,expected_head=task.head_digest)

    def snapshot(self, task):
        return self.store.task_snapshot(task.task_id,expected_request_digest=task.request_digest)

    def count(self, table):
        with sqlite3.connect(self.path) as db:return db.execute('SELECT count(*) FROM '+table).fetchone()[0]

    def test_submit_complete_replay_idempotence_and_scope(self):
        q = self.submit(); self.assertEqual(q,self.submit())
        self.assertEqual(q.verification_scope,'task-lifecycle-only')
        with self.assertRaisesRegex(LocalEvidenceError,'M3_TASK_RESULT_UNAVAILABLE'): self.result(q)
        done = self.run_task(q); self.assertEqual(done.state,'completed')
        self.assertEqual(self.submit(),done); self.assertEqual(self.run_task(done),done)
        self.assertEqual(self.count('task_events'),3)
        r = self.result(done); self.assertEqual(r.status,'verified_local')
        m = json.loads(r.manifest_json)
        proof = json.loads(json.loads(m['nodes'][3]['payload_json'])['result_json'])['proof']
        self.assertEqual((proof['relation'],proof['coverage_completeness']),('partial','complete'))
        with self.assertRaisesRegex(LocalEvidenceError,'M3_TASK_HEAD_CONFLICT'): self.run_task(q)
        with self.assertRaisesRegex(LocalEvidenceError,'M3_TASK_ID_CONFLICT'): self.submit(include_outside=False)
        with sqlite3.connect(self.path) as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],4)

    def test_explicit_cache_replays_and_never_falls_back(self):
        first = self.run_task(self.submit())
        cached = self.submit('cached',expected_graph_digest=first.graph_digest)
        with patch.object(self.store,'derive_graph',side_effect=AssertionError('must not derive')):
            done = self.run_task(cached)
        self.assertEqual(done.state,'completed'); self.assertEqual(done.graph_digest,first.graph_digest)
        wrong = self.submit('wrong',expected_graph_digest=first.graph_digest,include_outside=False)
        with patch.object(self.store,'derive_graph',side_effect=AssertionError('must not derive')):
            failed = self.run_task(wrong)
        self.assertEqual((failed.state,failed.failure_code),('failed','M3_GRAPH_SELECTOR_MISMATCH'))
        self.assertEqual(self.count('graphs'),1)
        # Completed task status is not permission to trust a modified snapshot.
        with sqlite3.connect(self.path) as db:db.execute('UPDATE graphs SET manifest=?',(b'{}',))
        with self.assertRaisesRegex(LocalEvidenceError,'M3_GRAPH_CORRUPT'): self.result(done)
        with self.assertRaisesRegex(LocalEvidenceError,'M3_GRAPH_CORRUPT'): self.run_task(done)

    def test_failure_and_retry_preserve_attempts(self):
        q = self.submit()
        with patch.object(self.store,'derive_graph',side_effect=LocalEvidenceError('M3_GRAPH_LIMIT_EXCEEDED')):
            failed = self.run_task(q)
        self.assertEqual((failed.state,failed.failure_code),('failed','M3_GRAPH_LIMIT_EXCEEDED'))
        self.assertEqual(self.count('graphs'),0)
        done = self.run_task(failed); self.assertEqual(done.state,'completed')
        history=self.store.task_history(done.task_id,expected_request_digest=done.request_digest,expected_head=done.head_digest)
        states=[e['state'] for e in json.loads(history)]
        self.assertEqual(states,['queued','running','failed','running','completed'])

    def test_runtime_failure_is_recorded_but_not_silently_swallowed(self):
        q = self.submit()
        with patch.object(self.store,'derive_graph',side_effect=RuntimeError('unexpected')):
            with self.assertRaisesRegex(RuntimeError,'unexpected'):self.run_task(q)
        self.assertEqual(self.snapshot(q).failure_code,'M3_TASK_EXECUTION_FAILED')

    def test_artifact_change_refuses_old_task_and_completed_result(self):
        q = self.submit()
        with patch('target_area_route_reconstruction.local_tasks._artifacts',return_value='0'*64):
            failed = self.run_task(q)
        self.assertEqual(failed.failure_code,'M3_TASK_ARTIFACT_MISMATCH')
        done = self.run_task(failed)
        with patch('target_area_route_reconstruction.local_tasks._artifacts',return_value='0'*64):
            with self.assertRaisesRegex(LocalEvidenceError,'M3_TASK_ARTIFACT_MISMATCH'):self.result(done)
            with self.assertRaisesRegex(LocalEvidenceError,'M3_TASK_ID_CONFLICT'):self.submit()

    def test_input_types_and_reserved_terminal_capacity(self):
        from dataclasses import dataclass
        @dataclass
        class Foreign: value: str = 'task'
        for value in (False,0,0.0,-0.0,Foreign()):
            with self.assertRaisesRegex(LocalEvidenceError,'M3_TASK_INPUT_INVALID'):self.submit(task_id=value)
            with self.assertRaisesRegex(LocalEvidenceError,'M3_TASK_INPUT_INVALID'):self.submit(max_source_bytes=value)
            with self.assertRaisesRegex(LocalEvidenceError,'M3_TASK_INPUT_INVALID'):self.submit(expected_graph_digest=value)
        q=self.submit()
        with patch('target_area_route_reconstruction.local_tasks.EVENT_LIMIT',2):
            with self.assertRaisesRegex(LocalEvidenceError,'M3_TASK_LIMIT_EXCEEDED'):self.run_task(q)
        self.assertEqual(self.snapshot(q).state,'queued')
        self.assertEqual(self.count('task_events'),1)

    def test_fenced_live_worker_cannot_complete_recovered_attempt(self):
        q=self.submit(); real=self.store.derive_graph; recovered=[]
        def interrupted(*args,**kwargs):
            running=self.snapshot(q)
            recovered.append(self.store.recover_task('task',expected_request_digest=q.request_digest,expected_head=running.head_digest,actor='operator'))
            return real(*args,**kwargs)
        with patch.object(self.store,'derive_graph',side_effect=interrupted):
            with self.assertRaisesRegex(LocalEvidenceError,'M3_TASK_HEAD_CONFLICT'):self.run_task(q)
        self.assertEqual(self.snapshot(q),recovered[0]);self.assertEqual(self.count('graphs'),1)
        done=self.run_task(recovered[0]);self.assertEqual(done.state,'completed');self.assertEqual(self.count('graphs'),1)

    def test_cold_process_and_concurrent_claim(self):
        q=self.submit()
        code='''import sys;from target_area_route_reconstruction import LocalTaskStore,LocalEvidenceError
try:
 r=LocalTaskStore(sys.argv[1]).run_task('task',expected_request_digest=sys.argv[2],expected_head=sys.argv[3],actor='child');print(r.state)
except LocalEvidenceError as e:print(e.code)
'''
        children=[subprocess.Popen([sys.executable,'-c',code,str(self.path),q.request_digest,q.head_digest],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
        results=[]
        for child in children:
            out,err=child.communicate(timeout=60);self.assertEqual(child.returncode,0,err);results.append(out.strip())
        self.assertCountEqual(results,['completed','M3_TASK_HEAD_CONFLICT'])
        done=self.snapshot(q);self.assertEqual(self.count('task_events'),3)
        read='''import sys;from target_area_route_reconstruction import LocalTaskStore
r=LocalTaskStore(sys.argv[1]).task_result('task',expected_request_digest=sys.argv[2],expected_head=sys.argv[3]);assert r.status=='verified_local';print(r.verification_scope)'''
        run=subprocess.run([sys.executable,'-c',read,str(self.path),q.request_digest,done.head_digest],capture_output=True,text=True,timeout=60)
        self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(run.stdout.strip(),'m2a-m2f')

    def test_crash_after_graph_before_task_completion_recovers_without_duplicates(self):
        q=self.submit()
        code='''import os,sys;from target_area_route_reconstruction import LocalTaskStore
s=LocalTaskStore(sys.argv[1]);real=s.derive_graph
def die(*a,**k):
 real(*a,**k);os._exit(77)
s.derive_graph=die
s.run_task('task',expected_request_digest=sys.argv[2],expected_head=sys.argv[3],actor='child')'''
        run=subprocess.run([sys.executable,'-c',code,str(self.path),q.request_digest,q.head_digest],capture_output=True,text=True,timeout=60)
        self.assertEqual(run.returncode,77,run.stderr)
        running=self.snapshot(q);self.assertEqual(running.state,'running');self.assertEqual(self.count('graphs'),1)
        with self.assertRaisesRegex(LocalEvidenceError,'M3_TASK_RESULT_UNAVAILABLE'):self.result(running)
        recovered=self.store.recover_task('task',expected_request_digest=q.request_digest,expected_head=running.head_digest,actor='operator')
        done=self.run_task(recovered);self.assertEqual(done.state,'completed');self.assertEqual(self.count('graphs'),1)

    def test_terminal_commit_crash_before_after_and_retry(self):
        code = """import json,os,sqlite3,sys
from target_area_route_reconstruction import LocalTaskStore
s=LocalTaskStore(sys.argv[1]);original=sqlite3.connect
class C(sqlite3.Connection):
 def commit(self):
  row=self.execute('SELECT record FROM task_events WHERE task_id=? ORDER BY sequence DESC LIMIT 1',(sys.argv[2],)).fetchone()
  terminal=row and json.loads(row[0])['state']=='completed'
  if terminal and sys.argv[5]=='before':os._exit(77)
  super().commit()
  if terminal:os._exit(78)
def connect(*a,**k):return original(*a,**k,factory=C)
sqlite3.connect=connect
s.run_task(sys.argv[2],expected_request_digest=sys.argv[3],expected_head=sys.argv[4],actor='child')
"""
        for when in ('before','after'):
            q=self.submit('terminal-'+when)
            run=subprocess.run([sys.executable,'-c',code,str(self.path),q.task_id,q.request_digest,q.head_digest,when],capture_output=True,text=True,timeout=60)
            self.assertEqual(run.returncode,77 if when=='before' else 78,run.stderr)
            state=self.snapshot(q)
            if when=='before':
                self.assertEqual(state.state,'running')
                state=self.store.recover_task(q.task_id,expected_request_digest=q.request_digest,expected_head=state.head_digest,actor='operator')
                state=self.run_task(state)
            self.assertEqual(state.state,'completed')
            self.assertEqual(self.run_task(state),state)
            self.assertEqual(self.result(state).status,'verified_local')
        self.assertEqual(self.count('graphs'),1)

    def test_v3_migration_preserves_graph_and_manual_review(self):
        from target_area_route_reconstruction import LocalReviewStore
        path=Path(self.tmp.name)/'v3.db';old=LocalReviewStore(path)
        a=old.admit_file(FIXTURES/'equivalent/basic.gpx',source_kind='gpx',track_source=SOURCE)
        g=old.derive_graph('s','r',expected_record_digest=a.record_digest,target_area=AREA)
        d=old.append_decision(g.graph_digest,scope='review',expected_head=None,decision_id='d',actor='reviewer',reason='Preserve audit',timestamp='2026-10-14T12:00:00.000000Z',relation='outside',expected_source_digest=a.record_digest,target_area=AREA)
        tables=('admissions','graphs','reviews')
        with sqlite3.connect(path) as db:before={t:db.execute('SELECT * FROM '+t).fetchall() for t in tables}
        new=LocalTaskStore(path)
        with sqlite3.connect(path) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],4)
            for t in tables:self.assertEqual(db.execute('SELECT * FROM '+t).fetchall(),before[t])
        self.assertEqual(new.effective_review(g.graph_digest,scope='review',expected_head=d.digest,expected_source_digest=a.record_digest,target_area=AREA).effective_relation,'outside')

    def test_corrupt_request_journal_and_rehashed_invalid_event(self):
        q=self.submit()
        with sqlite3.connect(self.path) as db: original=db.execute('SELECT record FROM task_events').fetchone()[0]
        e=json.loads(original);e['state']='completed';e['graph_digest']='0'*64
        forged=json.dumps(e,sort_keys=True,separators=(',',':')).encode()
        with sqlite3.connect(self.path) as db:db.execute('UPDATE task_events SET record=?,digest=?',(forged,hashlib.sha256(forged).hexdigest()))
        with self.assertRaisesRegex(LocalEvidenceError,'M3_TASK_CORRUPT'):self.snapshot(q)
        with sqlite3.connect(self.path) as db:
            db.execute('UPDATE task_events SET record=?,digest=?',(original,q.head_digest))
            db.execute('UPDATE tasks SET request=?',(b'{}',))
        with self.assertRaisesRegex(LocalEvidenceError,'M3_TASK_CORRUPT'):self.run_task(q)

    def test_negative_evaluation_is_completed_without_invented_success(self):
        raw=b'<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="task"/>'
        a=self.store.admit_bytes(raw,source_kind='gpx',track_source=SOURCE|{'id':'empty'})
        q=self.store.submit_task('empty','empty','r',actor='submitter',expected_record_digest=a.record_digest,target_area=AREA)
        done=self.run_task(q);self.assertEqual(done.state,'completed')
        r=self.result(done);m=json.loads(r.manifest_json)
        self.assertEqual(m['outcome'],'stage_unavailable')
        self.assertEqual(json.loads(m['nodes'][-1]['payload_json'])['outcome'],'unavailable')


if __name__=='__main__':unittest.main()
