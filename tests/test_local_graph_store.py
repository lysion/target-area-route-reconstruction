"""Independent graph selectors, cold replay, tampering and publication failures."""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace, asdict
from pathlib import Path
from unittest.mock import patch

from target_area_route_reconstruction import LocalGraphStore, LocalEvidenceStore, LocalEvidenceError, QualityPolicy
from target_area_route_reconstruction.local_graph import graph_artifacts
from target_area_route_reconstruction.local_graph import LEGACY_ENCODING
from target_area_route_reconstruction.local_evidence import canonical_record, _sha

ROOT=Path(__file__).resolve().parent.parent
FIXTURES=Path(os.environ.get('M3_SOURCE_FIXTURES',ROOT/'tests/source-fixtures'))


def source(kind='gpx'):
    return {'schema_version':'0.1.0','id':'s','revision_id':'r1','activity':{'id':'a'},'origin':{'namespace':'local'},'representation':{'media_type':'application/gpx+xml' if kind=='gpx' else 'application/vnd.ant.fit'}}


def area(revision='r1',x0=112.902,x1=112.908):
    return {'schema_version':'0.1.0','id':'t','revision_id':revision,'spatial_reference':'OGC:CRS84',
            'geometry':{'type':'Polygon','coordinates':[[[x0,28.19],[x1,28.19],[x1,28.22],[x0,28.22],[x0,28.19]]]},
            'definition_provenance':{'description':'Independent graph test'}}


class LocalGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'s.db';self.store=LocalGraphStore(self.path)
        self.admission=self.store.admit_file(FIXTURES/'equivalent/basic.gpx',source_kind='gpx',track_source=source())

    def derive(self,**kwargs):
        return self.store.derive_graph('s','r1',expected_record_digest=self.admission.record_digest,target_area=kwargs.pop('target_area',area()),**kwargs)

    def reload(self,commit,**kwargs):
        return self.store.reload_graph(commit.graph_digest,expected_source_digest=self.admission.record_digest,target_area=kwargs.pop('target_area',area()),**kwargs)

    def count(self):
        with sqlite3.connect(self.path) as db:return db.execute('SELECT count(*) FROM graphs').fetchone()[0]

    def manifest(self,commit):
        r=self.reload(commit);self.assertEqual(r.status,'verified_local');self.assertEqual(r.verification_scope,'m2a-m2f')
        return json.loads(r.manifest_json)

    def test_complete_nodes_exact_public_payloads_and_idempotence(self):
        commit=self.derive();self.assertEqual(commit,self.derive())
        m=self.manifest(commit)
        self.assertEqual([n['kind'] for n in m['nodes']],['request','M2A','M2B','M2C','M2D','M2E','M2F'])
        stage={n['kind']:json.loads(n['payload_json']) for n in m['nodes']}
        self.assertEqual([stage[k]['outcome'] for k in ('M2B','M2C','M2D','M2E','M2F')],['produced']*5)
        for kind in ('M2B','M2C','M2D'):
            self.assertEqual(json.loads(stage[kind]['verification_json'])['outcome'],'valid')
        # Frozen expected fixture spatial facts, not producer output as oracle.
        proof=json.loads(stage['M2C']['result_json'])['proof']
        self.assertEqual((proof['relation'],proof['coverage_completeness']),('partial','complete'))
        bundle=json.loads(stage['M2D']['result_json'])['bundle']
        self.assertEqual(len(bundle['segment_json']),1)
        temporal=json.loads(json.loads(stage['M2F']['result_json'])['geojson_json'])
        self.assertEqual(sum(f['properties']['layer']=='target_metric_edge' for f in temporal['features']),2)
        self.assertEqual(self.count(),1)

    def test_legacy_v1_graph_is_preserved_as_unverified_after_profile_identity_upgrade(self):
        commit = self.derive()
        with sqlite3.connect(self.path) as db:
            encoded = db.execute('SELECT manifest FROM graphs WHERE digest=?',
                                 (commit.graph_digest,)).fetchone()[0]
            manifest = json.loads(encoded)
            manifest['encoding'] = LEGACY_ENCODING
            manifest['request'].pop('resource_profile')
            manifest['request_digest'] = _sha(canonical_record(manifest['request']))
            previous = []
            for node in manifest['nodes']:
                if node['kind'] == 'request':
                    node['payload_json'] = canonical_record(manifest['request']).decode('utf-8')
                node['parents'] = [manifest['source']['admission_digest'], *previous]
                node['sha256'] = _sha(canonical_record({k: node[k] for k in ('kind','parents','payload_json')}))
                previous.append(node['sha256'])
            legacy_bytes = canonical_record(manifest)
            legacy_digest = _sha(legacy_bytes)
            db.execute('UPDATE graphs SET digest=?,request_digest=?,manifest=? WHERE digest=?',
                       (legacy_digest, manifest['request_digest'], legacy_bytes, commit.graph_digest))
        result = self.store.reload_graph(legacy_digest, expected_source_digest=self.admission.record_digest,
                                        target_area=area())
        self.assertEqual(result.status, 'historical_unverified')
        self.assertEqual(result.issues, ('legacy_graph_encoding',))

    def test_multiple_candidates_require_explicit_full_selectors(self):
        first=self.derive();second=self.derive(target_area=area('r2',112.9,112.909));third=self.derive(policy=QualityPolicy(max_implied_speed_mps=1000))
        self.assertEqual(len({first.graph_digest,second.graph_digest,third.graph_digest}),3)
        self.assertEqual(len(self.store.graph_candidates('s','r1')),3)
        with self.assertRaisesRegex(LocalEvidenceError,"M3_SOURCE_REFERENCE_INVALID"):
            self.store.graph_candidates(False,"r1")
        with self.assertRaisesRegex(LocalEvidenceError,'M3_GRAPH_SELECTOR_MISMATCH'):
            self.reload(first,target_area=area('r2',112.9,112.909))
        with self.assertRaisesRegex(LocalEvidenceError,'M3_GRAPH_SELECTOR_MISMATCH'):
            self.reload(first,include_outside=False)
        with self.assertRaisesRegex(LocalEvidenceError,'M3_GRAPH_SELECTOR_MISMATCH'):
            self.store.reload_graph(first.graph_digest,expected_source_digest='0'*64,target_area=area())
        self.assertEqual(self.reload(second,target_area=area('r2',112.9,112.909)).status,'verified_local')

    def test_policy_numeric_aliases_options_and_disabled_temporal(self):
        a=self.derive(policy=QualityPolicy(max_implied_speed_mps=1000))
        self.assertEqual(a,self.derive(policy=QualityPolicy(max_implied_speed_mps=1000.0)))
        disabled=self.derive(temporal_mode=None)
        result=self.reload(disabled,temporal_mode=None)
        self.assertEqual(json.loads(json.loads(result.manifest_json)['nodes'][-1]['payload_json'])['outcome'],'disabled')
        for option in (False,0,0.0):
            with self.assertRaisesRegex(LocalEvidenceError,'M3_GRAPH_OPTIONS_INVALID'):
                self.derive(temporal_mode=option)
        for option in (0,0.0):
            with self.assertRaisesRegex(LocalEvidenceError,'M3_GRAPH_OPTIONS_INVALID'):
                self.derive(include_outside=option)

    def test_real_fit_negative_gap_and_missing_time_cold_reload(self):
        for i,name in enumerate(('equivalent/basic.fit','gpx/discontinuity.gpx','gpx/no-timestamps.gpx','fit/no-position.fit','gpx/malformed.gpx')):
            path=Path(self.temp.name)/f'real-{i}.db';kind=Path(name).suffix[1:];store=LocalGraphStore(path)
            a=store.admit_file(FIXTURES/name,source_kind=kind,track_source=source(kind))
            g=store.derive_graph('s','r1',expected_record_digest=a.record_digest,target_area=area())
            code='''import json,sys; from target_area_route_reconstruction import LocalGraphStore
r=LocalGraphStore(sys.argv[1]).reload_graph(sys.argv[2],expected_source_digest=sys.argv[3],target_area=json.loads(sys.argv[4]));assert r.status=="verified_local";print(r.manifest_json)'''
            run=subprocess.run([sys.executable,'-c',code,str(path),g.graph_digest,a.record_digest,json.dumps(area())],capture_output=True,text=True,timeout=60)
            self.assertEqual(run.returncode,0,run.stderr);m=json.loads(run.stdout)
            stages={n['kind']:json.loads(n['payload_json']) for n in m['nodes']}
            if name in ('fit/no-position.fit','gpx/malformed.gpx'):
                self.assertEqual(m['outcome'],'stage_unavailable')
                self.assertEqual(stages['M2F']['outcome'],'unavailable')
            elif name=='gpx/no-timestamps.gpx':
                output=json.loads(json.loads(stages['M2F']['result_json'])['geojson_json'])
                metrics=[f['properties']['metric'] for f in output['features'] if f['properties']['layer']=='target_metric_edge']
                self.assertTrue(all(metric['status']!='valid' for metric in metrics))
            elif name=='gpx/discontinuity.gpx':
                proof=json.loads(stages['M2C']['result_json'])['proof']
                self.assertEqual(proof['coverage_completeness'],'incomplete')

    def test_exact_positive_unrepresentable_coverage_is_explicit_stage_failure(self):
        from fractions import Fraction
        raw=b'<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="math"><trk><trkseg><trkpt lat="0" lon="-1"/><trkpt lat="0" lon="1"/></trkseg></trk></gpx>'
        thin=area();thin['geometry']['coordinates']=[[[0,-1],[5e-324,-1],[5e-324,1],[0,1],[0,-1]]]
        exact_width=Fraction(float(5e-324))/2
        self.assertGreater(exact_width,0)
        store=LocalGraphStore(Path(self.temp.name)/'thin.db');a=store.admit_bytes(raw,source_kind='gpx',track_source=source())
        g=store.derive_graph('s','r1',expected_record_digest=a.record_digest,target_area=thin)
        r=store.reload_graph(g.graph_digest,expected_source_digest=a.record_digest,target_area=thin)
        m=json.loads(r.manifest_json);stages={n['kind']:json.loads(n['payload_json']) for n in m['nodes']}
        self.assertEqual(m['outcome'],'stage_unavailable')
        self.assertEqual(stages['M2C']['outcome'],'numerical_failure')
        self.assertEqual(stages['M2D']['outcome'],'unavailable')
        self.assertEqual(stages['M2F']['outcome'],'unavailable')

    def test_f4_allocated_time_and_parent_screen_survive_graph_reload(self):
        raw=b'<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="f4"><trk><trkseg><trkpt lat="80" lon="-89"><time>2026-10-12T00:00:00Z</time></trkpt><trkpt lat="80" lon="89"><time>2026-10-13T00:00:00Z</time></trkpt></trkseg></trk></gpx>'
        t=area();t['geometry']['coordinates']=[[[-1,79],[1,79],[1,81],[-1,81],[-1,79]]]
        store=LocalGraphStore(Path(self.temp.name)/'f4.db');a=store.admit_bytes(raw,source_kind='gpx',track_source=source())
        policy=QualityPolicy(max_implied_speed_mps=30)
        g=store.derive_graph('s','r1',expected_record_digest=a.record_digest,target_area=t,policy=policy)
        r=store.reload_graph(g.graph_digest,expected_source_digest=a.record_digest,target_area=t,policy=policy)
        nodes=json.loads(r.manifest_json)['nodes'];stage=json.loads(nodes[-1]['payload_json'])
        fc=json.loads(json.loads(stage['result_json'])['geojson_json'])
        edges=[f['properties'] for f in fc['features'] if f['properties']['layer']=='target_metric_edge']
        self.assertTrue(edges)
        self.assertGreater(edges[0]['metric']['speed_mps'],30)
        self.assertEqual(edges[0]['speed_screen_result'],'passed')
        self.assertEqual(edges[0]['metric']['duration_basis'],'proportional_parent_edge_allocation')

    def test_node_tamper_and_self_consistent_rehash_cannot_replace_expected_graph(self):
        g=self.derive();m=self.manifest(g)
        with sqlite3.connect(self.path) as db:
            raw=db.execute('SELECT manifest FROM graphs WHERE digest=?',(g.graph_digest,)).fetchone()[0]
            db.execute('UPDATE graphs SET manifest=? WHERE digest=?',(raw+b' ',g.graph_digest))
        with self.assertRaisesRegex(LocalEvidenceError,'M3_GRAPH_CORRUPT'):self.reload(g)
        # Rebuild every node hash after modifying the spatial verdict. Independent
        # test JSON encoder, not production graph hashing or validators.
        payload=json.loads(m['nodes'][3]['payload_json']);c=json.loads(payload['result_json']);c['proof']['relation']='outside'
        payload['result_json']=json.dumps(c,sort_keys=True,separators=(',',':'))
        m['nodes'][3]['payload_json']=json.dumps(payload,sort_keys=True,separators=(',',':'))
        seen=[]
        for n in m['nodes']:
            n['parents']=[self.admission.record_digest,*seen]
            envelope={k:n[k] for k in ('kind','parents','payload_json')}
            n['sha256']=hashlib.sha256(json.dumps(envelope,sort_keys=True,separators=(',',':')).encode()).hexdigest();seen.append(n['sha256'])
        encoded=json.dumps(m,sort_keys=True,separators=(',',':')).encode();digest=hashlib.sha256(encoded).hexdigest()
        with sqlite3.connect(self.path) as db:
            db.execute('DELETE FROM graphs')
            db.execute('INSERT INTO graphs VALUES (?,?,?,?)',(digest,self.admission.record_digest,m['request_digest'],encoded))
        with self.assertRaisesRegex(LocalEvidenceError,'M3_GRAPH_NOT_FOUND'):self.reload(g)
        with self.assertRaisesRegex(LocalEvidenceError,'M3_GRAPH_REPLAY_MISMATCH'):
            self.store.reload_graph(digest,expected_source_digest=self.admission.record_digest,target_area=area())

    def test_artifact_unavailable_or_changed_never_returns_verified_manifest(self):
        g=self.derive()
        for fake in (None,{'same_version':'different_bytes'}):
            with patch('target_area_route_reconstruction.local_graph.graph_artifacts',side_effect=OSError('absent') if fake is None else None,return_value=fake):
                result=self.reload(g);self.assertEqual(result.status,'historical_unverified');self.assertIsNone(result.manifest_json)

    def test_invalid_verifier_and_limit_failure_never_publish_graph(self):
        from target_area_route_reconstruction.quality_models import QualityVerification
        with patch('target_area_route_reconstruction.local_graph.verify_quality',return_value=QualityVerification('invalid')):
            with self.assertRaisesRegex(LocalEvidenceError,'M3_QUALITY_VERIFICATION_FAILED'):self.derive()
        self.assertEqual(self.count(),0)
        from target_area_route_reconstruction.resource_limits import DEFAULT_TASK_RESOURCE_PROFILE
        with self.assertRaisesRegex(LocalEvidenceError,'M3_GRAPH_LIMIT_EXCEEDED'):
            self.derive(resource_profile=replace(DEFAULT_TASK_RESOURCE_PROFILE, max_graph_bytes=1))
        self.assertEqual(self.count(),0)
        self.assertEqual(self.store.reload_source('s','r1',expected_record_digest=self.admission.record_digest).status,'verified_local')

    def test_concurrent_identical_derivations_publish_once(self):
        code="""import json,sys;from target_area_route_reconstruction import LocalGraphStore
r=LocalGraphStore(sys.argv[1]).derive_graph('s','r1',expected_record_digest=sys.argv[2],target_area=json.loads(sys.argv[3]));print(r.graph_digest)"""
        children=[subprocess.Popen([sys.executable,'-c',code,str(self.path),self.admission.record_digest,json.dumps(area())],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
        values=[]
        for child in children:
            out,err=child.communicate(timeout=60);self.assertEqual(child.returncode,0,err);values.append(out.strip())
        self.assertEqual(values[0],values[1]);self.assertEqual(self.count(),1)
        self.assertEqual(self.reload(self.derive()).status,'verified_local')

    def test_graph_publish_crash_before_and_after_commit(self):
        script='''import json,os,sqlite3,sys;from target_area_route_reconstruction import LocalGraphStore
s=LocalGraphStore(sys.argv[1]);original=sqlite3.connect
class C(sqlite3.Connection):
 def commit(self):
  if sys.argv[5]=="before":os._exit(77)
  super().commit();os._exit(78)
def connect(*a,**k):return original(*a,**k,factory=C)
sqlite3.connect=connect
s.derive_graph("s","r1",expected_record_digest=sys.argv[2],target_area=json.loads(sys.argv[3]),temporal_mode=sys.argv[4])'''
        for when,expected in (('before',0),('after',1)):
            run=subprocess.run([sys.executable,'-c',script,str(self.path),self.admission.record_digest,json.dumps(area()),'speed_mps',when],capture_output=True,text=True,timeout=60)
            self.assertEqual(run.returncode,77 if when=='before' else 78,run.stderr);self.assertEqual(self.count(),expected)
        self.assertEqual(self.reload(self.derive()).status,'verified_local')

    def test_legacy_source_material_can_derive_new_graph_without_relabeling_old_snapshot(self):
        # Simulate a genuine past artifact set at admission; old M2A verification
        # stays unavailable while new explicit graph freshly evaluates raw bytes.
        path=Path(self.temp.name)/'past.db'
        with patch('target_area_route_reconstruction.local_evidence.parser_artifacts',return_value={'past':'artifact-set'}):
            old=LocalEvidenceStore(path);a=old.admit_file(FIXTURES/'equivalent/basic.gpx',source_kind='gpx',track_source=source())
        self.assertEqual(old.reload_source('s','r1',expected_record_digest=a.record_digest).status,'historical_unverified')
        current=LocalGraphStore(path);g=current.derive_graph('s','r1',expected_record_digest=a.record_digest,target_area=area())
        self.assertEqual(current.reload_graph(g.graph_digest,expected_source_digest=a.record_digest,target_area=area()).status,'verified_local')
        self.assertEqual(current.reload_source('s','r1',expected_record_digest=a.record_digest).status,'historical_unverified')


if __name__=='__main__':unittest.main()
