"""Bounded basic-local backup snapshots, integrity scans and quarantine copies."""
from __future__ import annotations

import hashlib
import json
from contextlib import closing
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile
from dataclasses import dataclass
from urllib.parse import quote

from .ingestion import MAX_SOURCE_BYTES
from .local_evidence import LocalEvidenceError, RECORD_BYTES_LIMIT, LocalEvidenceStore, _sha, _source, canonical_record
from .resource_limits import GRAPH_BYTES_LIMIT
from .local_graph import LocalGraphStore
from .local_review import LocalReviewStore
from .local_tasks import LocalTaskStore, _hex
from .strict_json import loads_json

MAX_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024
SQLITE_TABLES = {
    'blobs': ('digest','data'),
    'admissions': ('source_id','revision_id','record_digest','raw_digest','record'),
    'graphs': ('digest','source_digest','request_digest','manifest'),
    'reviews': ('sequence','decision_id','digest','graph_digest','scope','record'),
    'tasks': ('task_id','request_digest','source_digest','request'),
    'task_events': ('sequence','task_id','digest','record'),
}

SQLITE_DDL = {
    'blobs': 'CREATE TABLE blobs (digest TEXT PRIMARY KEY, data BLOB NOT NULL)',
    'admissions': 'CREATE TABLE admissions (source_id TEXT NOT NULL, revision_id TEXT NOT NULL, record_digest TEXT NOT NULL UNIQUE, raw_digest TEXT NOT NULL REFERENCES blobs(digest), record BLOB NOT NULL, PRIMARY KEY(source_id, revision_id))',
    'graphs': 'CREATE TABLE graphs (digest TEXT PRIMARY KEY, source_digest TEXT NOT NULL REFERENCES admissions(record_digest), request_digest TEXT NOT NULL, manifest BLOB NOT NULL)',
    'reviews': 'CREATE TABLE reviews (sequence INTEGER PRIMARY KEY, decision_id TEXT NOT NULL UNIQUE, digest TEXT NOT NULL UNIQUE, graph_digest TEXT NOT NULL REFERENCES graphs(digest), scope TEXT NOT NULL, record BLOB NOT NULL)',
    'tasks': 'CREATE TABLE tasks (task_id TEXT PRIMARY KEY, request_digest TEXT NOT NULL, source_digest TEXT NOT NULL REFERENCES admissions(record_digest), request BLOB NOT NULL)',
    'task_events': 'CREATE TABLE task_events (sequence INTEGER PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id), digest TEXT NOT NULL UNIQUE, record BLOB NOT NULL)',
    'review_stream': 'CREATE INDEX review_stream ON reviews(graph_digest,scope,sequence)',
    'task_journal': 'CREATE INDEX task_journal ON task_events(task_id,sequence)',
}


class LocalArchiveError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class BackupInfo:
    path: str
    sha256: str
    byte_length: int
    schema_version: int = 4


@dataclass(frozen=True)
class QuarantineInfo:
    path: str
    sha256: str
    byte_length: int
    actor: str
    reason: str
    verification_scope: str = 'local-preservation-only'


def _regular(path):
    p = Path(path)
    try:
        mode = p.lstat().st_mode
    except FileNotFoundError:
        raise LocalArchiveError('M3_ARCHIVE_NOT_FOUND') from None
    if not stat.S_ISREG(mode):
        raise LocalArchiveError('M3_ARCHIVE_PATH_INVALID')
    return p


def _digest_file(path):
    p = _regular(path)
    size = p.stat().st_size
    if not 0 < size <= MAX_ARCHIVE_BYTES:
        raise LocalArchiveError('M3_ARCHIVE_LIMIT_EXCEEDED')
    h = hashlib.sha256()
    try:
        fd = os.open(p, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(fd, 'rb') as stream:
            while block := stream.read(1024 * 1024):
                h.update(block)
    except OSError as exc:
        raise LocalArchiveError('M3_ARCHIVE_READ_FAILED') from exc
    return h.hexdigest(), size


def _fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _readonly(path):
    p = _regular(path).resolve()
    return sqlite3.connect('file:' + quote(str(p), safe='/') + '?mode=ro', uri=True)


def _scan(path):
    """Validate bounded structural/hash closure without trusting any model output."""
    digest, size = _digest_file(path)
    try:
        with closing(_readonly(path)) as db:
            if db.execute('PRAGMA user_version').fetchone()[0] != 4:
                raise LocalArchiveError('M3_ARCHIVE_SCHEMA_UNSUPPORTED')
            page_size = db.execute('PRAGMA page_size').fetchone()[0]
            if db.execute('PRAGMA page_count').fetchone()[0] * page_size > MAX_ARCHIVE_BYTES:
                raise LocalArchiveError('M3_ARCHIVE_LIMIT_EXCEEDED')
            result = db.execute('PRAGMA integrity_check').fetchone()
            if result != ('ok',):
                raise LocalArchiveError('M3_ARCHIVE_CORRUPT')
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            if tables != set(SQLITE_TABLES):
                raise LocalArchiveError('M3_ARCHIVE_SCHEMA_UNSUPPORTED')
            ddl={name:sql for name,sql in db.execute("SELECT name,sql FROM sqlite_master WHERE type IN ('table','index') AND name NOT LIKE 'sqlite_%'")}
            if ddl != SQLITE_DDL:
                raise LocalArchiveError('M3_ARCHIVE_SCHEMA_UNSUPPORTED')
            for table, expected in SQLITE_TABLES.items():
                actual = tuple(r[1] for r in db.execute('PRAGMA table_info("' + table + '")'))
                if actual != expected:
                    raise LocalArchiveError('M3_ARCHIVE_SCHEMA_UNSUPPORTED')
            expected_fields = {
                'blobs': (('digest','TEXT',0,1),('data','BLOB',1,0)),
                'admissions': (('source_id','TEXT',1,1),('revision_id','TEXT',1,2),('record_digest','TEXT',1,0),('raw_digest','TEXT',1,0),('record','BLOB',1,0)),
                'graphs': (('digest','TEXT',0,1),('source_digest','TEXT',1,0),('request_digest','TEXT',1,0),('manifest','BLOB',1,0)),
                'reviews': (('sequence','INTEGER',0,1),('decision_id','TEXT',1,0),('digest','TEXT',1,0),('graph_digest','TEXT',1,0),('scope','TEXT',1,0),('record','BLOB',1,0)),
                'tasks': (('task_id','TEXT',0,1),('request_digest','TEXT',1,0),('source_digest','TEXT',1,0),('request','BLOB',1,0)),
                'task_events': (('sequence','INTEGER',0,1),('task_id','TEXT',1,0),('digest','TEXT',1,0),('record','BLOB',1,0)),
            }
            for table, fields in expected_fields.items():
                actual=tuple((r[1],r[2].upper(),r[3],r[5]) for r in db.execute('PRAGMA table_info("'+table+'")'))
                if actual!=fields:
                    raise LocalArchiveError('M3_ARCHIVE_SCHEMA_UNSUPPORTED')
            expected_fks={
                'admissions': {('blobs','raw_digest','digest')},
                'graphs': {('admissions','source_digest','record_digest')},
                'reviews': {('graphs','graph_digest','digest')},
                'tasks': {('admissions','source_digest','record_digest')},
                'task_events': {('tasks','task_id','task_id')},
                'blobs': set(),
            }
            for table, expected in expected_fks.items():
                actual={(r[2],r[3],r[4]) for r in db.execute('PRAGMA foreign_key_list("'+table+'")')}
                if actual!=expected:
                    raise LocalArchiveError('M3_ARCHIVE_SCHEMA_UNSUPPORTED')
            if db.execute('PRAGMA foreign_key_check').fetchone() is not None:
                raise LocalArchiveError('M3_ARCHIVE_CORRUPT')
            indexes = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")}
            if indexes != {'review_stream','task_journal'}:
                raise LocalArchiveError('M3_ARCHIVE_SCHEMA_UNSUPPORTED')
            if db.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view') LIMIT 1").fetchone():
                raise LocalArchiveError('M3_ARCHIVE_SCHEMA_UNSUPPORTED')
            expected_indexes = {'review_stream': ('graph_digest','scope','sequence'),
                                'task_journal': ('task_id','sequence')}
            for name, columns in expected_indexes.items():
                actual = tuple(r[2] for r in db.execute('PRAGMA index_info("' + name + '")'))
                if actual != columns:
                    raise LocalArchiveError('M3_ARCHIVE_SCHEMA_UNSUPPORTED')
            expected_unique = {'blobs': {('digest',)},
                               'admissions': {('source_id','revision_id'),('record_digest',)},
                               'graphs': {('digest',)},
                               'reviews': {('digest',),('decision_id',)},
                               'tasks': {('task_id',)},
                               'task_events': {('digest',)}}
            for table, required in expected_unique.items():
                actual = set()
                for index in db.execute('PRAGMA index_list("' + table + '")'):
                    if index[2]:
                        actual.add(tuple(r[2] for r in db.execute('PRAGMA index_info("' + index[1] + '")')))
                if actual != required:
                    raise LocalArchiveError('M3_ARCHIVE_SCHEMA_UNSUPPORTED')
            for table, column in (('blobs','digest'),('graphs','digest'),('admissions','record_digest'),
                                  ('reviews','digest'),('reviews','decision_id'),('tasks','task_id'),
                                  ('task_events','digest')):
                total, distinct = db.execute('SELECT COUNT(*),COUNT(DISTINCT "' + column + '") FROM "' + table + '"').fetchone()
                if total != distinct:
                    raise LocalArchiveError('M3_ARCHIVE_CORRUPT')
            total = db.execute('SELECT COUNT(*) FROM admissions').fetchone()[0]
            distinct = db.execute('SELECT COUNT(*) FROM (SELECT source_id,revision_id FROM admissions GROUP BY source_id,revision_id)').fetchone()[0]
            if total != distinct:
                raise LocalArchiveError('M3_ARCHIVE_CORRUPT')
            blobs = {}
            for key, blob in db.execute('SELECT digest,CASE WHEN typeof(data)=\'blob\' AND length(data)<=? THEN data ELSE NULL END FROM blobs', (MAX_SOURCE_BYTES,)):
                if type(key) is not str or not _hex(key) or type(blob) is not bytes or _sha(blob) != key:
                    raise LocalArchiveError('M3_ARCHIVE_CORRUPT')
                blobs[key] = len(blob)
            admissions = {}
            for sid, rev, rd, rawd, payload in db.execute('SELECT source_id,revision_id,record_digest,raw_digest,CASE WHEN typeof(record)=\'blob\' AND length(record)<=? THEN record ELSE NULL END FROM admissions', (RECORD_BYTES_LIMIT,)):
                record = LocalEvidenceStore._decode((sid,rev,rd,rawd,payload))
                rawlen = blobs.get(rawd)
                if (rawlen is None or type(record['raw'].get('byte_length')) is not int or record['raw']['byte_length'] != rawlen
                        or _source(record['source'],record['source_kind'],rawd) != record['source']):
                    raise LocalArchiveError('M3_ARCHIVE_CORRUPT')
                admissions[rd] = record
            graphs = {}
            for row in db.execute('SELECT digest,source_digest,request_digest,CASE WHEN typeof(manifest)=\'blob\' AND length(manifest)<=? THEN manifest ELSE NULL END FROM graphs', (GRAPH_BYTES_LIMIT,)):
                digest_key, source_digest, request_digest, _ = row
                manifest = LocalGraphStore._decode_graph(row)
                source = admissions.get(source_digest)
                if source is None:
                    raise LocalArchiveError('M3_ARCHIVE_CORRUPT')
                if (manifest['source']['admission_digest'] != source_digest
                        or manifest['source']['id'] != source['source']['id']
                        or manifest['source']['revision_id'] != source['source']['revision_id']):
                    raise LocalArchiveError('M3_ARCHIVE_CORRUPT')
                graphs[digest_key] = manifest
            for graph_digest, scope in db.execute('SELECT DISTINCT graph_digest,scope FROM reviews'):
                manifest = graphs.get(graph_digest)
                if manifest is None or type(scope) is not str:
                    raise LocalArchiveError('M3_ARCHIVE_CORRUPT')
                node = loads_json(manifest['nodes'][4]['payload_json'])
                result = loads_json(node['result_json']) if node['result_json'] is not None else None
                bundle = result.get('bundle') if result else None
                if type(bundle) is not dict or type(bundle.get('assessment_json')) is not str:
                    raise LocalArchiveError('M3_ARCHIVE_CORRUPT')
                assessment = loads_json(bundle['assessment_json'])
                ref = {k: assessment[k] for k in ('id','revision_id')}
                LocalReviewStore._history(db, graph_digest, scope, ref)
            for task_id, request_digest, source_digest in db.execute('SELECT task_id,request_digest,source_digest FROM tasks'):
                request = LocalTaskStore._load(db, task_id, request_digest)
                source = admissions.get(source_digest)
                if source is None or request['source']['admission_digest'] != source_digest:
                    raise LocalArchiveError('M3_ARCHIVE_CORRUPT')
                if (request['source']['id'] != source['source']['id']
                        or request['source']['revision_id'] != source['source']['revision_id']):
                    raise LocalArchiveError('M3_ARCHIVE_CORRUPT')
                state, _history = LocalTaskStore._events(db,task_id,request_digest)
                if state.state == 'completed':
                    manifest = graphs.get(state.graph_digest)
                    if (manifest is None or manifest['source'] != request['source']
                            or _sha(canonical_record(manifest['artifacts'])) != request['artifacts_digest']
                            or canonical_record(manifest['request']) != canonical_record(request['graph_request'])):
                        raise LocalArchiveError('M3_ARCHIVE_CORRUPT')
    except LocalArchiveError:
        raise
    except (sqlite3.Error, LocalEvidenceError, KeyError, TypeError, ValueError, RecursionError) as exc:
        raise LocalArchiveError('M3_ARCHIVE_CORRUPT') from exc
    return BackupInfo(str(Path(path)), digest, size)


class LocalArchiveStore(LocalTaskStore):
    def inspect_backup(self, path):
        return _scan(path)

    def create_backup(self, destination):
        source = _regular(self.path)
        parent = Path(destination).parent
        if not parent.is_dir() or Path(destination).exists() or Path(destination).is_symlink():
            raise LocalArchiveError('M3_BACKUP_DESTINATION_INVALID')
        _scan(source)
        fd, temp = tempfile.mkstemp(prefix='.m3-backup-', dir=parent)
        os.close(fd)
        try:
            try:
                src = _readonly(source)
                dst = sqlite3.connect(temp)
                try:
                    page_size = src.execute('PRAGMA page_size').fetchone()[0]
                    dst.execute('PRAGMA max_page_count=' + str(max(1, MAX_ARCHIVE_BYTES // page_size)))
                    src.backup(dst, pages=256, sleep=0.01)
                    dst.commit()
                finally:
                    dst.close(); src.close()
                if os.path.getsize(temp) > MAX_ARCHIVE_BYTES:
                    raise LocalArchiveError('M3_ARCHIVE_LIMIT_EXCEEDED')
                with open(temp,'rb') as stream: os.fsync(stream.fileno())
                _scan(temp)
                os.link(temp,destination,follow_symlinks=False)
                _fsync_dir(parent)
                return _scan(destination)
            except FileExistsError as exc:
                raise LocalArchiveError('M3_BACKUP_DESTINATION_EXISTS') from exc
            except LocalArchiveError:
                raise
            except (OSError, sqlite3.Error) as exc:
                raise LocalArchiveError('M3_BACKUP_FAILED') from exc
        finally:
            try: os.unlink(temp)
            except FileNotFoundError: pass

    def restore_backup(self, backup, destination):
        info = _scan(backup)
        parent = Path(destination).parent
        if not parent.is_dir() or Path(destination).exists() or Path(destination).is_symlink():
            raise LocalArchiveError('M3_RESTORE_DESTINATION_INVALID')
        fd,temp=tempfile.mkstemp(prefix='.m3-restore-',dir=parent);os.close(fd)
        try:
            try:
                with open(backup,'rb') as src, open(temp,'wb') as dst:
                    shutil.copyfileobj(src,dst,1024*1024);dst.flush();os.fsync(dst.fileno())
                if _scan(temp).sha256 != info.sha256:
                    raise LocalArchiveError('M3_RESTORE_COPY_MISMATCH')
                os.link(temp,destination,follow_symlinks=False);_fsync_dir(parent)
                return _scan(destination)
            except FileExistsError as exc:
                raise LocalArchiveError('M3_RESTORE_DESTINATION_EXISTS') from exc
            except LocalArchiveError:
                raise
            except OSError as exc:
                raise LocalArchiveError('M3_RESTORE_FAILED') from exc
        finally:
            try:os.unlink(temp)
            except FileNotFoundError:pass

    def quarantine_file(self, candidate, directory, *, expected_sha256, actor, reason):
        path=_regular(candidate);digest,size=_digest_file(path)
        if not _hex(expected_sha256) or digest != expected_sha256:
            raise LocalArchiveError('M3_QUARANTINE_DIGEST_MISMATCH')
        for value in (actor,reason):
            try:
                if type(value) is not str or not value.strip(): raise ValueError
                if len(value.encode('utf-8',errors='strict'))>4096: raise ValueError
                canonical_record(value)
            except (ValueError,UnicodeError) as exc:
                raise LocalArchiveError('M3_QUARANTINE_INPUT_INVALID') from exc
        root=Path(directory)
        try:root.mkdir(mode=0o700,parents=True,exist_ok=True)
        except OSError as exc:raise LocalArchiveError('M3_QUARANTINE_FAILED') from exc
        final=root/digest
        try:final.mkdir(mode=0o700)
        except FileExistsError:
            return self.inspect_quarantine(final,expected_sha256=digest,actor=actor,reason=reason)
        try:
            tmp=final/'.evidence.tmp';dest=final/'evidence.bin'
            with open(path,'rb') as src,open(tmp,'xb') as out:
                shutil.copyfileobj(src,out,1024*1024);out.flush();os.fsync(out.fileno())
            os.replace(tmp,dest)
            manifest={'encoding':'m3-local-quarantine-v1','sha256':digest,'byte_length':size,'filename':'evidence.bin','actor':actor,'reason':reason}
            encoded=canonical_record(manifest)
            mtmp=final/'.manifest.tmp';mpath=final/'manifest.json'
            with open(mtmp,'xb') as out:out.write(encoded);out.flush();os.fsync(out.fileno())
            os.link(mtmp,mpath,follow_symlinks=False);os.unlink(mtmp);_fsync_dir(final);_fsync_dir(root)
            return self.inspect_quarantine(final,expected_sha256=digest,actor=actor,reason=reason)
        except (OSError,LocalArchiveError) as exc:
            if isinstance(exc,LocalArchiveError):raise
            raise LocalArchiveError('M3_QUARANTINE_FAILED') from exc

    @staticmethod
    def inspect_quarantine(directory, *, expected_sha256, actor=None, reason=None):
        root=Path(directory)
        if root.is_symlink() or not root.is_dir():raise LocalArchiveError('M3_QUARANTINE_INCOMPLETE')
        try:
            manifest_path=root/'manifest.json'
            mode=manifest_path.lstat().st_mode
            if not stat.S_ISREG(mode) or manifest_path.stat().st_size>65536:
                raise LocalArchiveError('M3_QUARANTINE_CORRUPT')
            fd=os.open(manifest_path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
            with os.fdopen(fd,'rb') as stream:
                encoded_manifest=stream.read(65537)
                manifest=loads_json(encoded_manifest)
            if (type(manifest) is not dict or set(manifest)!={'encoding','sha256','byte_length','filename','actor','reason'}
                    or canonical_record(manifest)!=encoded_manifest or type(manifest['encoding']) is not str
                    or manifest['encoding']!='m3-local-quarantine-v1' or type(manifest['filename']) is not str
                    or manifest['filename']!='evidence.bin' or type(manifest['sha256']) is not str
                    or type(manifest['byte_length']) is not int or type(manifest['actor']) is not str
                    or not manifest['actor'].strip() or type(manifest['reason']) is not str or not manifest['reason'].strip()
                    or manifest['sha256']!=expected_sha256 or root.name!=expected_sha256):
                raise LocalArchiveError('M3_QUARANTINE_CORRUPT')
            digest,size=_digest_file(root/'evidence.bin')
            if digest!=expected_sha256 or size!=manifest['byte_length']:
                raise LocalArchiveError('M3_QUARANTINE_CORRUPT')
            if actor is not None and actor!=manifest['actor'] or reason is not None and reason!=manifest['reason']:
                raise LocalArchiveError('M3_QUARANTINE_CONFLICT')
            return QuarantineInfo(str(root),digest,size,manifest['actor'],manifest['reason'])
        except LocalArchiveError:raise
        except (OSError,ValueError,TypeError,KeyError) as exc:
            raise LocalArchiveError('M3_QUARANTINE_INCOMPLETE') from exc
