"""M3A real source, process restart, concurrency and crash admission witnesses."""
import hashlib
import json
import os
import sqlite3
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from target_area_route_reconstruction import ingest_bytes
from target_area_route_reconstruction.local_evidence import (
    LocalEvidenceStore, LocalEvidenceError, canonical_record,
)

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(os.environ.get("M3_SOURCE_FIXTURES", ROOT / "tests/source-fixtures"))
GPX = b'<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="m3"><trk><trkseg><trkpt lat="0" lon="0"/><trkpt lat="0" lon="1"/></trkseg></trk></gpx>'


def source(sid="s", activity="a", kind="gpx"):
    return {"schema_version":"0.1.0", "id":sid, "revision_id":"r1", "activity":{"id":activity},
            "origin":{"namespace":"local_import"}, "representation":{"media_type":
            "application/gpx+xml" if kind=="gpx" else "application/vnd.ant.fit"}}


class LocalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "evidence.sqlite"
        self.store = LocalEvidenceStore(self.path)

    def counts(self):
        with sqlite3.connect(self.path) as db:
            return tuple(db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in ("blobs", "admissions"))

    def test_encoding_aliases_and_forbidden_objects(self):
        self.assertEqual(canonical_record({"x":False,"z":0.0}), b'{"x":false,"z":0}')
        self.assertEqual(canonical_record({"n":-0.0}), canonical_record({"n":0}))
        self.assertEqual(canonical_record({"n":1.0}), canonical_record({"n":1}))
        self.assertNotEqual(canonical_record({"n":False}), canonical_record({"n":0}))
        class Foreign(dict):
            def items(self):
                raise AssertionError("no subclass codec callback")
        for value in (Foreign(x=1), (1,), float('nan'), float('inf'), {"x":"\ud800"}, {1:0}):
            with self.subTest(value=repr(value)), self.assertRaises(LocalEvidenceError):
                canonical_record(value)

    def test_idempotence_dedup_conflict_and_full_source(self):
        first = self.store.admit_bytes(GPX, source_kind="gpx", track_source=source())
        self.assertEqual(first, self.store.admit_bytes(GPX, source_kind="gpx", track_source=source()))
        other = self.store.admit_bytes(GPX, source_kind="gpx", track_source=source("other", "other-activity"))
        self.assertNotEqual(first.record_digest, other.record_digest)
        self.assertEqual(self.counts(), (1,2))
        for altered in (source(activity="changed"), {**source(), "origin":{"namespace":"changed"}},
                        {**source(),"extensions":{"audit":"changed"}}):
            with self.assertRaisesRegex(LocalEvidenceError, "M3_SOURCE_CONFLICT"):
                self.store.admit_bytes(GPX, source_kind="gpx", track_source=altered)
        with self.assertRaisesRegex(LocalEvidenceError,"M3_SOURCE_CONFLICT"):
            self.store.admit_bytes(GPX+b' ', source_kind="gpx", track_source=source())
        reloaded = self.store.reload_source("s", "r1", expected_record_digest=first.record_digest)
        self.assertEqual(reloaded.status, "verified_local")
        self.assertEqual(reloaded.verification_scope,"source-and-m2a")
        self.assertEqual(json.loads(reloaded.track_source_json),source())
        expected=ingest_bytes(GPX,source_kind="gpx",track_source={"id":"s","revision_id":"r1"})
        self.assertEqual(reloaded.ingestion.to_json(),expected.to_json())

    def test_file_entry_retains_bounded_read_failures(self):
        path=Path(self.directory.name)/"source.gpx"
        path.write_bytes(GPX)
        with self.assertRaisesRegex(LocalEvidenceError,"SOURCE_BYTES_LIMIT_EXCEEDED"):
            self.store.admit_file(path,source_kind="gpx",track_source=source(),max_source_bytes=len(GPX)-1)
        with self.assertRaisesRegex(LocalEvidenceError,"SOURCE_READ_FAILED"):
            self.store.admit_file(path.with_name("absent"),source_kind="gpx",track_source=source())
        if hasattr(os,"mkfifo"):
            fifo=path.with_name("fifo");os.mkfifo(fifo)
            with self.assertRaisesRegex(LocalEvidenceError,"SOURCE_NOT_REGULAR_FILE"):
                self.store.admit_file(fifo,source_kind="fit",track_source=source(kind="fit"))
        self.assertEqual(self.counts(),(0,0))

    def test_json_aliases_preserve_admission_identity(self):
        a={**source(),"extensions":{"number":0,"bool":False}}
        b={**source(),"extensions":{"number":-0.0,"bool":False}}
        first=self.store.admit_bytes(GPX,source_kind="gpx",track_source=a)
        self.assertEqual(first,self.store.admit_bytes(GPX,source_kind="gpx",track_source=b))
        b["extensions"]["bool"]=0
        with self.assertRaisesRegex(LocalEvidenceError,"M3_SOURCE_CONFLICT"):
            self.store.admit_bytes(GPX,source_kind="gpx",track_source=b)

    def test_admission_budget_hash_schema_and_profile(self):
        with patch('target_area_route_reconstruction.local_evidence._sha',side_effect=AssertionError("no over-budget hash")):
            with self.assertRaisesRegex(LocalEvidenceError,"SOURCE_BYTES_LIMIT_EXCEEDED"):
                self.store.admit_bytes(GPX,source_kind="gpx",track_source=source(),max_source_bytes=len(GPX)-1)
        for limit in (False,0,0.0,-1,256*1024*1024+1):
            with self.assertRaisesRegex(LocalEvidenceError,"INVALID_SOURCE_BYTES_LIMIT"):
                self.store.admit_bytes(GPX,source_kind="gpx",track_source=source(),max_source_bytes=limit)
        invalid={**source(),"activity":{"id":"a","revision_id":"not-allowed"}}
        with self.assertRaisesRegex(LocalEvidenceError,"M3_SOURCE_INVALID"):
            self.store.admit_bytes(GPX,source_kind="gpx",track_source=invalid)
        mismatch=source();mismatch['representation']['content_hash']={"algorithm":"sha256","digest":"0"*64}
        with self.assertRaisesRegex(LocalEvidenceError,"SOURCE_HASH_MISMATCH"):
            self.store.admit_bytes(GPX,source_kind="gpx",track_source=mismatch)
        with self.assertRaisesRegex(LocalEvidenceError,"trust_backend_unavailable"):
            LocalEvidenceStore(self.path,profile="enhanced-custody")
        self.assertEqual(self.counts(),(0,0))

    def test_corruption_and_expected_selector(self):
        first=self.store.admit_bytes(GPX,source_kind="gpx",track_source=source())
        with self.assertRaisesRegex(LocalEvidenceError,"M3_EXPECTED_RECORD_MISMATCH"):
            self.store.reload_source("s","r1",expected_record_digest="0"*64)
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE blobs SET data=?",(b'x'*len(GPX),))
        with self.assertRaisesRegex(LocalEvidenceError,"M3_STORE_CORRUPT"):
            self.store.reload_source("s","r1",expected_record_digest=first.record_digest)
        self.assertEqual(self.counts(),(1,1))

    def test_recomputed_m2a_snapshot_is_rejected_by_fresh_reingestion(self):
        first=self.store.admit_bytes(GPX,source_kind="gpx",track_source=source())
        with sqlite3.connect(self.path) as db:
            raw=db.execute("SELECT record FROM admissions").fetchone()[0]
            record=json.loads(raw)
            evidence=json.loads(record['ingestion_json'])
            evidence['canonical_track']['parts'][0]['observations'][0]['position']=[40.0,30.0]
            record['ingestion_json']=json.dumps(evidence,sort_keys=True,separators=(',',':'),ensure_ascii=False)
            changed=json.dumps(record,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
            digest=hashlib.sha256(changed).hexdigest()
            db.execute("UPDATE admissions SET record=?,record_digest=?",(changed,digest))
        # Original separately retained expectation catches self-consistent rewriting.
        with self.assertRaisesRegex(LocalEvidenceError,"M3_EXPECTED_RECORD_MISMATCH"):
            self.store.reload_source('s','r1',expected_record_digest=first.record_digest)
        # Even a caller choosing the new digest cannot skip original-byte replay.
        with self.assertRaisesRegex(LocalEvidenceError,"M3_REINGEST_MISMATCH"):
            self.store.reload_source('s','r1',expected_record_digest=digest)

    def test_stored_json_strict_admission_and_unknown_schema(self):
        first=self.store.admit_bytes(GPX,source_kind="gpx",track_source=source())
        for raw in (b'{"x":1,"x":2}',b'{"x":1e-400}',b'{"x":NaN}',b'{"x":"\\ud800"}'):
            digest=hashlib.sha256(raw).hexdigest()
            with sqlite3.connect(self.path) as db:
                db.execute("UPDATE admissions SET record=?,record_digest=?",(raw,digest))
            with self.assertRaisesRegex(LocalEvidenceError,"M3_STORE_CORRUPT"):
                self.store.reload_source('s','r1',expected_record_digest=digest)
        with sqlite3.connect(self.path) as db:
            db.execute('PRAGMA user_version=999')
        with self.assertRaisesRegex(LocalEvidenceError,'M3_SCHEMA_UNAVAILABLE'):
            LocalEvidenceStore(self.path)

    def test_parser_artifact_change_is_unverified_and_retry_does_not_overwrite(self):
        first=self.store.admit_bytes(GPX,source_kind="gpx",track_source=source())
        with patch('target_area_route_reconstruction.local_evidence.parser_artifacts',return_value={"different":"same-version-bytes"}):
            result=self.store.reload_source("s","r1",expected_record_digest=first.record_digest)
            self.assertEqual(result.status,"historical_unverified")
            self.assertIsNone(result.ingestion)
            self.assertEqual(first,self.store.admit_bytes(GPX,source_kind="gpx",track_source=source()))
        with patch('target_area_route_reconstruction.local_evidence.parser_artifacts',side_effect=OSError("unavailable")):
            result=self.store.reload_source("s","r1",expected_record_digest=first.record_digest)
            self.assertEqual(result.status,"historical_unverified")
            self.assertEqual(result.issues,("artifact_unavailable",))

    def test_actual_same_version_module_bytes_changed_in_isolated_copy(self):
        import target_area_route_reconstruction as package
        isolated=Path(self.directory.name)/'isolated'
        destination=isolated/'target_area_route_reconstruction'
        shutil.copytree(Path(package.__file__).parent,destination,ignore=shutil.ignore_patterns('__pycache__'))
        env={**os.environ,'PYTHONPATH':str(isolated),'PYTHONDONTWRITEBYTECODE':'1'}
        admit_code="""import json,sys; from target_area_route_reconstruction.local_evidence import LocalEvidenceStore
r=LocalEvidenceStore(sys.argv[1]).admit_bytes(bytes.fromhex(sys.argv[2]),source_kind="gpx",track_source=json.loads(sys.argv[3]));print(r.record_digest)"""
        run=subprocess.run([sys.executable,'-c',admit_code,str(self.path),GPX.hex(),json.dumps(source())],env=env,capture_output=True,text=True,timeout=30)
        self.assertEqual(run.returncode,0,run.stderr)
        digest=run.stdout.strip()
        changed=destination/'normalization.py'
        changed.write_text(changed.read_text()+'\n# Same advertised version, changed executable bytes.\n')
        reload_code="""import sys; from target_area_route_reconstruction.local_evidence import LocalEvidenceStore
r=LocalEvidenceStore(sys.argv[1]).reload_source('s','r1',expected_record_digest=sys.argv[2]);print(r.status);assert r.ingestion is None"""
        run=subprocess.run([sys.executable,'-c',reload_code,str(self.path),digest],env=env,capture_output=True,text=True,timeout=30)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(run.stdout.strip(),'historical_unverified')

    def test_real_fit_gpx_negative_and_new_process_reload(self):
        for i, name in enumerate(('equivalent/basic.fit','equivalent/basic.gpx','fit/no-position.fit','gpx/malformed.gpx','gpx/discontinuity.gpx','gpx/no-timestamps.gpx')):
            raw=(FIXTURES/name).read_bytes();kind=Path(name).suffix[1:];sid=f'real-{i}'
            receipt=self.store.admit_file(FIXTURES/name,source_kind=kind,track_source=source(sid,kind=kind))
            self.assertEqual((FIXTURES/name).read_bytes(),raw)
            expected=ingest_bytes(raw,source_kind=kind,track_source={"id":sid,"revision_id":"r1"})
            code='''import sys,hashlib; from target_area_route_reconstruction.local_evidence import LocalEvidenceStore
r=LocalEvidenceStore(sys.argv[1]).reload_source(sys.argv[2],"r1",expected_record_digest=sys.argv[3]); assert r.status=="verified_local"; print(hashlib.sha256(r.ingestion.to_json().encode()).hexdigest())'''
            run=subprocess.run([sys.executable,'-c',code,str(self.path),sid,receipt.record_digest],capture_output=True,text=True,timeout=30)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertEqual(run.stdout.strip(),hashlib.sha256(expected.to_json().encode()).hexdigest())
            self.assertEqual(receipt.outcome,expected.outcome)

    def test_concurrent_conflicting_processes(self):
        # Child processes contend for same full-source revision with different Activity.
        script='''import json,sys; from target_area_route_reconstruction.local_evidence import LocalEvidenceStore,LocalEvidenceError
try:
 r=LocalEvidenceStore(sys.argv[1]).admit_bytes(bytes.fromhex(sys.argv[2]),source_kind="gpx",track_source=json.loads(sys.argv[3])); print("committed")
except LocalEvidenceError as e:
 print(e.code)
'''
        children=[subprocess.Popen([sys.executable,'-c',script,str(self.path),GPX.hex(),json.dumps(source(activity=a))],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for a in ('a','b')]
        results=[]
        for child in children:
            out,err=child.communicate(timeout=30);self.assertEqual(child.returncode,0,err);results.append(out.strip())
        self.assertCountEqual(results,['committed','M3_SOURCE_CONFLICT'])
        self.assertEqual(self.counts(),(1,1))

    def test_process_death_before_and_after_transaction_commit(self):
        # Connection subclass injects a process exit at the actual public-entry commit.
        script='''import json,os,sqlite3,sys
from target_area_route_reconstruction.local_evidence import LocalEvidenceStore
s=LocalEvidenceStore(sys.argv[1]); original=sqlite3.connect
class Connection(sqlite3.Connection):
 def commit(self):
  if sys.argv[4]=="before": os._exit(77)
  super().commit(); os._exit(78)
def connect(*a,**k): return original(*a,**k,factory=Connection)
sqlite3.connect=connect
s.admit_bytes(bytes.fromhex(sys.argv[2]),source_kind="gpx",track_source=json.loads(sys.argv[3]))
'''
        for boundary,expected in (('before',(0,0)),('after',(1,1))):
            run=subprocess.run([sys.executable,'-c',script,str(self.path),GPX.hex(),json.dumps(source()),boundary],capture_output=True,text=True,timeout=30)
            self.assertEqual(run.returncode,77 if boundary=='before' else 78,run.stderr)
            LocalEvidenceStore(self.path)
            self.assertEqual(self.counts(),expected)
        receipt=self.store.admit_bytes(GPX,source_kind="gpx",track_source=source())
        self.assertEqual(self.store.reload_source('s','r1',expected_record_digest=receipt.record_digest).status,'verified_local')


if __name__=='__main__':
    unittest.main()
