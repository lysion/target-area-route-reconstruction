#!/usr/bin/env python3
"""Exercise the bounded persisted task path with 1,600 real GPX parts."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
import hashlib
from pathlib import Path

import shapely

from target_area_route_reconstruction import LocalTaskStore, TaskResourceProfile
from target_area_route_reconstruction.local_graph import graph_artifacts
from target_area_route_reconstruction.local_evidence import canonical_record

PARTS = 1600
DEFAULT_WALL_SECONDS = 90
DEFAULT_RSS_BYTES = 1024 * 1024 * 1024

SOURCE = {
    'schema_version': '0.1.0', 'id': 'm3-benchmark-source', 'revision_id': 'r1',
    'activity': {'id': 'm3-benchmark-activity'}, 'origin': {'namespace': 'local'},
    'representation': {'media_type': 'application/gpx+xml'},
}
AREA = {
    'schema_version': '0.1.0', 'id': 'm3-benchmark-target', 'revision_id': 'r1',
    'spatial_reference': 'OGC:CRS84',
    'geometry': {'type': 'Polygon', 'coordinates': [[[-0.5, -1], [0.5, -1],
                    [0.5, 1], [-0.5, 1], [-0.5, -1]]]},
    'definition_provenance': {'description': 'M3 1600-part F6 baseline'},
}


def _gpx():
    origin = datetime(2026, 1, 1, tzinfo=timezone.utc)
    segments = []
    for part in range(PARTS):
        start = (origin + timedelta(seconds=part * 2)).isoformat().replace('+00:00', 'Z')
        end = (origin + timedelta(seconds=part * 2 + 1)).isoformat().replace('+00:00', 'Z')
        segments.append(f'<trkseg><trkpt lat="0" lon="-1"><time>{start}</time></trkpt>'
                        f'<trkpt lat="0" lon="1"><time>{end}</time></trkpt></trkseg>')
    return ('<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="m3-benchmark">'
            '<trk><name>fragmented</name>' + ''.join(segments) + '</trk></gpx>').encode()


def _single():
    if '--debug' in sys.argv:
        from target_area_route_reconstruction import local_graph
        modules = [local_graph]
        from target_area_route_reconstruction import spatial, spatial_verifier, spatial_entities, spatial_entities_verifier, geojson_export, temporal_overlay, quality, quality_verifier
        modules.extend([spatial, spatial_verifier, spatial_entities, spatial_entities_verifier,
                        geojson_export, temporal_overlay, quality, quality_verifier])
        for module in modules:
            for name in ('project_quality', 'verify_quality', 'prove_spatial_relation',
                         'verify_spatial_relation', 'assemble_spatial_entities',
                         'verify_spatial_entities', 'export_geojson', 'export_temporal_geojson',
                         '_assemble', '_verify', '_verify_spatial_entities', '_maximal_covered',
                         '_expected_ranges'):
                original_method = getattr(module, name, None)
                if original_method is None or getattr(original_method, '_bench_wrapped', False):
                    continue
                def wrap(method, label):
                    def measured(*args, **kwargs):
                        started = time.monotonic()
                        try:
                            return method(*args, **kwargs)
                        finally:
                            print(json.dumps({'stage': label, 'seconds': time.monotonic() - started}),
                                  file=sys.stderr, flush=True)
                    measured._bench_wrapped = True
                    return measured
                setattr(module, name, wrap(original_method, module.__name__ + '.' + name))
        original = local_graph._pipeline
        def diagnostic_pipeline(*args, **kwargs):
            manifest = original(*args, **kwargs)
            print(json.dumps({'graph_payload_bytes': sum(len(node['payload_json']) for node in manifest['nodes']),
                              'nodes': [(node['kind'], len(node['payload_json'])) for node in manifest['nodes']]}),
                  file=sys.stderr)
            return manifest
        local_graph._pipeline = diagnostic_pipeline
    profile = TaskResourceProfile(max_observations=2 * PARTS, max_parts=PARTS,
        max_quality_fragments=10_000, max_target_vertices=20_000,
        max_output_vertices=250_000, max_wall_clock_seconds=DEFAULT_WALL_SECONDS,
        max_rss_bytes=DEFAULT_RSS_BYTES, max_graph_bytes=32 * 1024 * 1024)
    raw = _gpx()
    with tempfile.TemporaryDirectory(prefix='m3-f6-1600-') as directory:
        store = LocalTaskStore(os.path.join(directory, 'evidence.sqlite'))
        admitted = store.admit_bytes(raw, source_kind='gpx', track_source=SOURCE,
                                     max_source_bytes=len(raw))
        queued = store.submit_task('benchmark-1600', SOURCE['id'], SOURCE['revision_id'],
            actor='benchmark', expected_record_digest=admitted.record_digest,
            target_area=AREA, resource_profile=profile)
        started = time.monotonic()
        completed = store.run_task(queued.task_id, expected_request_digest=queued.request_digest,
                                   expected_head=queued.head_digest, actor='benchmark')
        task_seconds = time.monotonic() - started
        task_peak_rss = store._last_worker_peak_rss_bytes
        if completed.state != 'completed':
            raise RuntimeError('TASK_FAILED:' + str(completed.failure_code))
        started = time.monotonic()
        result = store.task_result(completed.task_id, expected_request_digest=completed.request_digest,
                                   expected_head=completed.head_digest)
        reload_seconds = time.monotonic() - started
        reload_peak_rss = store._last_worker_peak_rss_bytes
        if result.status != 'verified_local':
            raise RuntimeError('RELOAD_FAILED:' + str(result.status))
        return {
            'parts': PARTS, 'raw_bytes': len(raw),
            'task_seconds': task_seconds, 'task_worker_peak_rss_bytes': task_peak_rss,
            'reload_seconds': reload_seconds, 'reload_worker_peak_rss_bytes': reload_peak_rss,
            'python': sys.version, 'platform': platform.platform(),
            'cpu_model': _cpu_model(), 'cpu_affinity': _cpu_affinity(),
            'shapely': shapely.__version__, 'geos': shapely.geos_version_string,
            'artifact_manifest_sha256': hashlib.sha256(canonical_record(graph_artifacts())).hexdigest(),
            'git_head': subprocess.run(['git', 'rev-parse', 'HEAD'], check=True,
                                       capture_output=True, text=True).stdout.strip(),
            'worktree_code_sha256': _code_fingerprint(),
            'resource_profile': {
                'max_source_bytes': profile.max_source_bytes,
                'max_observations': profile.max_observations,
                'max_parts': profile.max_parts,
                'max_quality_fragments': profile.max_quality_fragments,
                'max_target_vertices': profile.max_target_vertices,
                'max_output_vertices': profile.max_output_vertices,
                'max_graph_bytes': profile.max_graph_bytes,
                'max_wall_clock_seconds': profile.max_wall_clock_seconds,
                'max_rss_bytes': profile.max_rss_bytes,
            },
        }


def _code_fingerprint():
    root = Path(__file__).resolve().parent.parent
    paths = sorted((root / 'src/target_area_route_reconstruction').glob('*.py'))
    paths.append(Path(__file__).resolve())
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode('utf-8') + b'\0')
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _cpu_model():
    try:
        with open('/proc/cpuinfo', encoding='ascii') as source:
            return next((line.split(':', 1)[1].strip() for line in source
                         if line.startswith('model name')), None)
    except OSError:
        return None


def _cpu_affinity():
    try:
        return sorted(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        return None


def main():
    if '--single' in sys.argv:
        result = _single()
        print(json.dumps(result, sort_keys=True))
        return
    results = []
    for _ in range(3):
        child = subprocess.run([sys.executable, __file__, '--single'], check=True,
                               capture_output=True, text=True, timeout=180)
        results.append(json.loads(child.stdout))
    report = {'clean_runs': results, 'default_wall_seconds': DEFAULT_WALL_SECONDS,
              'default_rss_bytes': DEFAULT_RSS_BYTES,
              'pass': all(row['task_seconds'] <= DEFAULT_WALL_SECONDS
                          and row['reload_seconds'] <= DEFAULT_WALL_SECONDS
                          and row['task_worker_peak_rss_bytes'] <= DEFAULT_RSS_BYTES
                          and row['reload_worker_peak_rss_bytes'] <= DEFAULT_RSS_BYTES
                          for row in results)}
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report['pass']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
