"""Snapshot/restore is no-overwrite; quarantine preserves raw suspect bytes."""
from pathlib import Path
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from target_area_route_reconstruction import LocalArchiveStore, LocalTaskStore, LocalArchiveError, LocalEvidenceError, QualityPolicy

FIXTURES=Path(os.environ.get('M3_SOURCE_FIXTURES',Path(__file__).resolve().parent/'source-fixtures'))
SOURCE={'schema_version':'0.1.0','id':'s','revision_id':'r','activity':{'id':'a'},'origin':{'namespace':'local'},'representation':{'media_type':'application/gpx+xml'}}
AREA={'schema_version':'0.1.0','id':'t','revision_id':'r','spatial_reference':'OGC:CRS84',
      'geometry':{'type':'Polygon','coordinates':[[[112.902,28.19],[112.908,28.19],[112.908,28.22],[112.902,28.22],[112.902,28.19]]]},
      'definition_provenance':{'description':'Archive integrity test'}}


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.db=self.root/'main.sqlite';self.store=LocalArchiveStore(self.db)

    def populate(self):
        a=self.store.admit_file(FIXTURES/'equivalent/basic.gpx',source_kind='gpx',track_source=SOURCE)
        g=self.store.derive_graph('s','r',expected_record_digest=a.record_digest,target_area=AREA)
        d=self.store.append_decision(g.graph_digest,scope='task',expected_head=None,decision_id='review',actor='reviewer',reason='Keep audit',timestamp='2026-10-14T12:00:00.000000Z',relation='outside',expected_source_digest=a.record_digest,target_area=AREA)
        q=self.store.submit_task('task','s','r',actor='submitter',expected_record_digest=a.record_digest,target_area=AREA,expected_graph_digest=g.graph_digest)
        done=self.store.run_task('task',expected_request_digest=q.request_digest,expected_head=q.head_digest,actor='worker')
        return a,g,d,done

    @staticmethod
    def counts(path):
        with sqlite3.connect(path) as db:
            return {table:db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ('blobs','admissions','graphs','reviews','tasks','task_events')}

    def test_snapshot_restore_preserves_full_domain_and_replays(self):
        a,g,d,done=self.populate();backup=self.root/'backup.sqlite'
        info=self.store.create_backup(backup)
        self.assertEqual(info.sha256,hashlib.sha256(backup.read_bytes()).hexdigest())
        self.assertEqual(self.store.inspect_backup(backup),info)
        restored=self.root/'restored.sqlite';restored_info=self.store.restore_backup(backup,restored)
        self.assertEqual(restored_info.sha256,info.sha256)
        expected={'blobs':1,'admissions':1,'graphs':1,'reviews':1,'tasks':1,'task_events':3}
        self.assertEqual(self.counts(self.db),expected);self.assertEqual(self.counts(backup),expected);self.assertEqual(self.counts(restored),expected)
        reader=LocalTaskStore(restored)
        self.assertEqual(reader.reload_source('s','r',expected_record_digest=a.record_digest).status,'verified_local')
        self.assertEqual(reader.reload_graph(g.graph_digest,expected_source_digest=a.record_digest,target_area=AREA).status,'verified_local')
        self.assertEqual(reader.effective_review(g.graph_digest,scope='task',expected_head=d.digest,expected_source_digest=a.record_digest,target_area=AREA).effective_relation,'outside')
        self.assertEqual(reader.task_result('task',expected_request_digest=done.request_digest,expected_head=done.head_digest).status,'verified_local')
        self.assertEqual(self.counts(self.db),expected)

    def test_no_overwrite_missing_paths_links_and_limits(self):
        backup=self.root/'backup.sqlite';self.store.create_backup(backup);before=backup.read_bytes()
        with self.assertRaisesRegex(LocalArchiveError,'M3_BACKUP_DESTINATION_INVALID'):self.store.create_backup(backup)
        with self.assertRaisesRegex(LocalArchiveError,'M3_RESTORE_DESTINATION_INVALID'):self.store.restore_backup(backup,self.db)
        symlink=self.root/'linked.sqlite';symlink.symlink_to(backup)
        with self.assertRaisesRegex(LocalArchiveError,'M3_ARCHIVE_PATH_INVALID'):self.store.inspect_backup(symlink)
        self.assertEqual(backup.read_bytes(),before)
        with self.assertRaisesRegex(LocalArchiveError,'M3_ARCHIVE_NOT_FOUND'):self.store.inspect_backup(self.root/'missing')
        (self.root/'wrong.sqlite').write_bytes(b'not sqlite')
        with self.assertRaisesRegex(LocalArchiveError,'M3_ARCHIVE_CORRUPT'):self.store.restore_backup(self.root/'wrong.sqlite',self.root/'rejected.sqlite')
        self.assertFalse((self.root/'rejected.sqlite').exists())

    def test_scan_detects_raw_database_corruption_and_schema_drift(self):
        a,_,_,_=self.populate();corrupt=self.root/'corrupt.sqlite'
        self.store.create_backup(corrupt)
        with sqlite3.connect(corrupt) as db:db.execute('UPDATE blobs SET data=?',(b'X'*100,))
        with self.assertRaisesRegex(LocalArchiveError,'M3_ARCHIVE_CORRUPT'):self.store.inspect_backup(corrupt)
        drift=self.root/'drift.sqlite';self.store.create_backup(drift)
        with sqlite3.connect(drift) as db:db.execute('PRAGMA user_version=99')
        with self.assertRaisesRegex(LocalArchiveError,'M3_ARCHIVE_SCHEMA_UNSUPPORTED'):self.store.inspect_backup(drift)
        trigger=self.root/'trigger.sqlite';self.store.create_backup(trigger)
        with sqlite3.connect(trigger) as db:db.execute('CREATE TRIGGER unexpected AFTER UPDATE ON tasks BEGIN SELECT 1; END')
        with self.assertRaisesRegex(LocalArchiveError,'M3_ARCHIVE_SCHEMA_UNSUPPORTED'):self.store.inspect_backup(trigger)
        no_fk=self.root/'no-fk.sqlite';self.store.create_backup(no_fk)
        with sqlite3.connect(no_fk) as db:
            db.execute('PRAGMA foreign_keys=OFF');db.execute('ALTER TABLE graphs RENAME TO old_graphs')
            db.execute('CREATE TABLE graphs (digest TEXT PRIMARY KEY,source_digest TEXT NOT NULL,request_digest TEXT NOT NULL,manifest BLOB NOT NULL)')
            db.execute('DROP TABLE old_graphs')
        with self.assertRaisesRegex(LocalArchiveError,'M3_ARCHIVE_SCHEMA_UNSUPPORTED'):self.store.inspect_backup(no_fk)
        altered=self.root/'altered-check.sqlite';self.store.create_backup(altered)
        with sqlite3.connect(altered) as db:
            db.execute('ALTER TABLE task_events RENAME TO old_events')
            db.execute('CREATE TABLE task_events (sequence INTEGER PRIMARY KEY CHECK(sequence>=0), task_id TEXT NOT NULL REFERENCES tasks(task_id), digest TEXT NOT NULL UNIQUE, record BLOB NOT NULL)')
            db.execute('DROP TABLE old_events');db.execute('CREATE INDEX task_journal ON task_events(task_id,sequence)')
        with self.assertRaisesRegex(LocalArchiveError,'M3_ARCHIVE_SCHEMA_UNSUPPORTED'):self.store.inspect_backup(altered)
        self.assertEqual(self.store.reload_source('s','r',expected_record_digest=a.record_digest).status,'verified_local')

    def test_scan_rejects_rehashed_boolean_byte_length(self):
        import json
        raw=b'x';small=LocalArchiveStore(self.root/'small.sqlite')
        small.admit_bytes(raw,source_kind='gpx',track_source=SOURCE)
        backup=self.root/'boolean-length.sqlite';small.create_backup(backup)
        with sqlite3.connect(backup) as db:
            digest,payload=db.execute('SELECT record_digest,record FROM admissions').fetchone()
            record=json.loads(payload);record['raw']['byte_length']=True
            forged=json.dumps(record,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
            replacement=hashlib.sha256(forged).hexdigest()
            db.execute('UPDATE admissions SET record_digest=?,record=? WHERE record_digest=?',(replacement,forged,digest))
        with self.assertRaisesRegex(LocalArchiveError,'M3_ARCHIVE_CORRUPT'):
            small.inspect_backup(backup)

    def test_quarantine_preserves_unopenable_candidate_and_checks_manifest(self):
        suspect=self.root/'suspect.bin';raw=b'not a valid SQLite or FIT file\x00\xff';suspect.write_bytes(raw)
        digest=hashlib.sha256(raw).hexdigest();quarantine=self.root/'quarantine'
        saved=self.store.quarantine_file(suspect,quarantine,expected_sha256=digest,actor='operator',reason='Suspect restore media')
        self.assertEqual((Path(saved.path)/'evidence.bin').read_bytes(),raw)
        self.assertEqual(self.store.inspect_quarantine(saved.path,expected_sha256=digest,actor='operator',reason='Suspect restore media'),saved)
        with self.assertRaisesRegex(LocalArchiveError,'M3_QUARANTINE_CONFLICT'):
            self.store.quarantine_file(suspect,quarantine,expected_sha256=digest,actor='operator',reason='Different decision')
        with self.assertRaisesRegex(LocalArchiveError,'M3_QUARANTINE_DIGEST_MISMATCH'):
            self.store.quarantine_file(suspect,quarantine,expected_sha256='0'*64,actor='operator',reason='wrong')
        self.assertEqual(suspect.read_bytes(),raw)
        (Path(saved.path)/'evidence.bin').write_bytes(b'changed')
        with self.assertRaisesRegex(LocalArchiveError,'M3_QUARANTINE_CORRUPT'):
            self.store.inspect_quarantine(saved.path,expected_sha256=digest)

    def test_quarantine_incomplete_and_symlink_candidates_refuse(self):
        suspect=self.root/'raw';suspect.write_bytes(b'preserve')
        digest=hashlib.sha256(suspect.read_bytes()).hexdigest();root=self.root/'q';incomplete=root/digest;incomplete.mkdir(parents=True)
        with self.assertRaisesRegex(LocalArchiveError,'M3_QUARANTINE_INCOMPLETE'):
            self.store.quarantine_file(suspect,root,expected_sha256=digest,actor='op',reason='crash recovery')
        link=self.root/'symlink';link.symlink_to(suspect)
        with self.assertRaisesRegex(LocalArchiveError,'M3_ARCHIVE_PATH_INVALID'):
            self.store.quarantine_file(link,root,expected_sha256=digest,actor='op',reason='reject link')
        self.assertEqual(suspect.read_bytes(),b'preserve')

    def test_quarantine_rejects_noncanonical_rehashed_manifest(self):
        suspect=self.root/'raw';suspect.write_bytes(b'quarantine record')
        digest=hashlib.sha256(suspect.read_bytes()).hexdigest()
        q=self.store.quarantine_file(suspect,self.root/'q',expected_sha256=digest,actor='op',reason='test')
        manifest=Path(q.path)/'manifest.json';m=json.loads(manifest.read_text());m['byte_length']=True
        manifest.write_text(json.dumps(m,sort_keys=True,separators=(',',':')))
        with self.assertRaisesRegex(LocalArchiveError,'M3_QUARANTINE_CORRUPT'):
            self.store.inspect_quarantine(q.path,expected_sha256=digest)

    def test_crash_before_and_after_backup_publication(self):
        script="""import os,sys
import target_area_route_reconstruction.local_archive as a
from target_area_route_reconstruction import LocalArchiveStore
real=a.os.link;target=sys.argv[2]
def hooked(src,dst,*args,**kwargs):
 if dst==target and sys.argv[3]=='before':os._exit(71)
 result=real(src,dst,*args,**kwargs)
 if dst==target:os._exit(72)
 return result
a.os.link=hooked
LocalArchiveStore(sys.argv[1]).create_backup(target)
"""
        for mode,code in (('before',71),('after',72)):
            dest=self.root/(mode+'.sqlite')
            run=subprocess.run([sys.executable,'-c',script,str(self.db),str(dest),mode],capture_output=True,text=True,timeout=60)
            self.assertEqual(run.returncode,code,run.stderr)
            if mode=='before':self.assertFalse(dest.exists())
            else:self.assertEqual(self.store.inspect_backup(dest).schema_version,4)
        self.assertEqual(self.store.inspect_backup(self.db).schema_version,4)

    def test_crash_during_quarantine_leaves_incomplete_preserved_copy(self):
        raw=self.root/'raw';raw.write_bytes(b'quarantine crash data');digest=hashlib.sha256(raw.read_bytes()).hexdigest();directory=self.root/'q'
        script="""import os,sys
import target_area_route_reconstruction.local_archive as a
from target_area_route_reconstruction import LocalArchiveStore
real=a.os.link;target=sys.argv[3]+'/'+sys.argv[4]+'/manifest.json'
def hooked(src,dst,*args,**kwargs):
 if os.fspath(dst)==target:os._exit(73)
 return real(src,dst,*args,**kwargs)
a.os.link=hooked
LocalArchiveStore(sys.argv[1]).quarantine_file(sys.argv[2],sys.argv[3],expected_sha256=sys.argv[4],actor='op',reason='crash')
"""
        run=subprocess.run([sys.executable,'-c',script,str(self.db),str(raw),str(directory),digest],capture_output=True,text=True,timeout=60)
        self.assertEqual(run.returncode,73,run.stderr)
        partial=directory/digest
        self.assertEqual((partial/'evidence.bin').read_bytes(),raw.read_bytes())
        with self.assertRaisesRegex(LocalArchiveError,'M3_QUARANTINE_INCOMPLETE'):
            self.store.inspect_quarantine(partial,expected_sha256=digest)
        with self.assertRaisesRegex(LocalArchiveError,'M3_QUARANTINE_INCOMPLETE'):
            self.store.quarantine_file(raw,directory,expected_sha256=digest,actor='op',reason='retry')
        self.assertEqual(raw.read_bytes(),b'quarantine crash data')


if __name__=='__main__':unittest.main()
