#!/usr/bin/env python3
"""Reproducible M2D producer/independent-verifier fragmentation benchmark.

The production functions are timed separately on valid, increasing parent
positions. Each clean run is a fresh Python process. Batches are fixed for all
sizes so sub-20ms individual timings are normalized without selecting a batch
after seeing a candidate result.
"""
from __future__ import annotations

import json
import hashlib
import os
import platform
import resource
import subprocess
import sys
import time
from types import SimpleNamespace

import shapely

from target_area_route_reconstruction.local_graph import graph_artifacts
from target_area_route_reconstruction.local_evidence import canonical_record
from target_area_route_reconstruction.models import TrackPosition
from target_area_route_reconstruction.quality_models import ParentInterval
from target_area_route_reconstruction.spatial_entities import _maximal_covered
from target_area_route_reconstruction.spatial_entities_verifier import _expected_ranges

SIZES = (200, 400, 800, 1600)
WARMUPS = 2
MEASUREMENTS = 7
BATCH_BY_SIZE = {200: 200, 400: 128, 800: 64, 1600: 32}
CLEAN_RUNS = 3


def _fixture(size):
    usable = tuple(ParentInterval(TrackPosition(part, 0), TrackPosition(part, 1))
                   for part in range(size))
    coverage = tuple(ParentInterval(TrackPosition(part, 0), TrackPosition(part, 1))
                     for part in range(size))
    proof = SimpleNamespace(target_coverage_intervals=coverage, stationary_evidence=())
    projection = SimpleNamespace(usable_intervals=usable)
    return {}, projection, proof


def _rss_limit_bytes():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


def _environment():
    model = None
    try:
        with open('/proc/cpuinfo', encoding='ascii') as cpuinfo:
            for line in cpuinfo:
                if line.startswith('model name'):
                    model = line.split(':', 1)[1].strip()
                    break
    except OSError:
        pass
    try:
        affinity = sorted(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        affinity = None
    source_files = (
        'src/target_area_route_reconstruction/spatial_entities.py',
        'src/target_area_route_reconstruction/spatial_entities_verifier.py',
        'src/target_area_route_reconstruction/_m2d_common.py',
        'scripts/benchmark_m3_fragmentation.py',
    )
    source_hash = hashlib.sha256()
    for filename in source_files:
        source_hash.update(filename.encode('utf-8') + b'\0')
        with open(filename, 'rb') as source:
            source_hash.update(hashlib.sha256(source.read()).digest())
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], check=True,
                          capture_output=True, text=True).stdout.strip()
    return {
        'git_head': head,
        'worktree_source_manifest_sha256': source_hash.hexdigest(),
        'source_files': list(source_files),
        'python': sys.version,
        'platform': platform.platform(),
        'cpu_model': model,
        'cpu_affinity': affinity,
        'shapely': shapely.__version__,
        'geos': shapely.geos_version_string,
        'artifact_manifest_sha256': hashlib.sha256(canonical_record(graph_artifacts())).hexdigest(),
        'batch_invocations_by_size': BATCH_BY_SIZE,
        'warmup_batches': WARMUPS,
        'measurement_batches': MEASUREMENTS,
    }


def _measure(function, args, batch):
    for _ in range(WARMUPS):
        for _ in range(batch):
            function(*args)
    samples = []
    raw_samples = []
    for _ in range(MEASUREMENTS):
        started = time.perf_counter()
        for _ in range(batch):
            function(*args)
        raw = time.perf_counter() - started
        raw_samples.append(raw)
        samples.append(raw / batch)
    if min(raw_samples) < 0.020:
        raise RuntimeError(f'CANDIDATE_TIMER_BELOW_20MS_REQUIRES_PREDECLARED_BATCH:{batch}:{min(raw_samples)}')
    return sorted(samples)[len(samples) // 2], samples, raw_samples


def _legacy_producer(track, projection, proof):
    """Frozen quadratic producer shape from the pre-indexed implementation."""
    output = []
    for usable in projection.usable_intervals:
        lower, upper = (usable.start.part_index, usable.start.observation_index), \
                       (usable.end.part_index, usable.end.observation_index)
        candidates = []
        for interval in proof.target_coverage_intervals:
            if lower <= (interval.start.part_index, interval.start.observation_index) and \
                    (interval.end.part_index, interval.end.observation_index) <= upper:
                candidates.append((interval.start, interval.end, True))
        for witness in proof.stationary_evidence:
            interval = witness.interval
            if witness.target_covered and lower <= (interval.start.part_index, interval.start.observation_index) and \
                    (interval.end.part_index, interval.end.observation_index) <= upper:
                candidates.append((interval.start, interval.end, False))
        candidates.sort(key=lambda item: ((item[0].part_index, item[0].observation_index),
                                         (item[1].part_index, item[1].observation_index)))
        current = None
        positive = False
        for start, end, is_positive in candidates:
            if current is None:
                current, positive = [start, end], is_positive
            elif (current[1].part_index, current[1].observation_index) == (start.part_index, start.observation_index):
                current[1], positive = end, positive or is_positive
            else:
                if positive:
                    output.append(tuple(current))
                current, positive = [start, end], is_positive
        if current is not None and positive:
            output.append(tuple(current))
    return tuple(output)


def _legacy_verifier(proof, quality):
    """Frozen independent quadratic sweep from the pre-indexed verifier."""
    result = []
    for usable in quality.usable_intervals:
        lower, upper = (usable.start.part_index, usable.start.observation_index), \
                       (usable.end.part_index, usable.end.observation_index)
        events = []
        for interval in proof.target_coverage_intervals:
            if lower <= (interval.start.part_index, interval.start.observation_index) and \
                    (interval.end.part_index, interval.end.observation_index) <= upper:
                events.append((interval.start, interval.end, 1))
        for witness in proof.stationary_evidence:
            if not witness.target_covered:
                continue
            interval = witness.interval
            if lower <= (interval.start.part_index, interval.start.observation_index) and \
                    (interval.end.part_index, interval.end.observation_index) <= upper:
                events.append((interval.start, interval.end, 0))
        events.sort(key=lambda event: ((event[0].part_index, event[0].observation_index),
                                       (event[1].part_index, event[1].observation_index)))
        block = []
        for event in events:
            if not block or (block[-1][1].part_index, block[-1][1].observation_index) == \
                    (event[0].part_index, event[0].observation_index):
                block.append(event)
            else:
                if any(item[2] for item in block):
                    result.append((block[0][0], block[-1][1]))
                block = [event]
        if block and any(item[2] for item in block):
            result.append((block[0][0], block[-1][1]))
    return tuple(result)


def _measure_legacy(function, args, batch):
    """Use fixed per-size batches so baseline samples exceed timer noise."""
    for _ in range(WARMUPS):
        for _ in range(batch):
            function(*args)
    samples = []
    raw_samples = []
    for _ in range(MEASUREMENTS):
        started = time.perf_counter()
        for _ in range(batch):
            function(*args)
        raw = time.perf_counter() - started
        raw_samples.append(raw)
        samples.append(raw / batch)
    if min(raw_samples) < 0.020:
        raise RuntimeError(f'LEGACY_TIMER_BELOW_20MS_REQUIRES_PREDECLARED_BATCH:{batch}:{min(raw_samples)}')
    return sorted(samples)[len(samples) // 2], samples, raw_samples


def _single_run():
    values = {'baseline': {'producer': {}, 'verifier': {}},
              'candidate': {'producer': {}, 'verifier': {}}}
    for size in SIZES:
        track, projection, proof = _fixture(size)
        args_producer = (track, projection, proof)
        args_verifier = (proof, projection)
        baseline_producer = _legacy_producer(*args_producer)
        baseline_verifier = _legacy_verifier(*args_verifier)
        candidate_producer = _maximal_covered(*args_producer)
        candidate_verifier = _expected_ranges(*args_verifier)
        assert baseline_producer == candidate_producer
        assert baseline_verifier == candidate_verifier
        batch = BATCH_BY_SIZE[size]
        legacy_producer_median, legacy_producer_samples, legacy_producer_raw = _measure_legacy(
            _legacy_producer, args_producer, batch)
        legacy_verifier_median, legacy_verifier_samples, legacy_verifier_raw = _measure_legacy(
            _legacy_verifier, args_verifier, batch)
        values['baseline']['producer'][str(size)] = {
            'median_seconds': legacy_producer_median,
            'samples_seconds': legacy_producer_samples,
            'raw_batch_seconds': legacy_producer_raw,
            'batch_invocations_per_sample': batch,
        }
        values['baseline']['verifier'][str(size)] = {
            'median_seconds': legacy_verifier_median,
            'samples_seconds': legacy_verifier_samples,
            'raw_batch_seconds': legacy_verifier_raw,
            'batch_invocations_per_sample': batch,
        }
        producer_median, producer_samples, producer_raw = _measure(
            _maximal_covered, args_producer, batch)
        verifier_median, verifier_samples, verifier_raw = _measure(
            _expected_ranges, args_verifier, batch)
        values['candidate']['producer'][str(size)] = {
            'median_seconds': producer_median,
            'samples_seconds': producer_samples,
            'raw_batch_seconds': producer_raw,
            'batch_invocations_per_sample': batch,
        }
        values['candidate']['verifier'][str(size)] = {
            'median_seconds': verifier_median,
            'samples_seconds': verifier_samples,
            'raw_batch_seconds': verifier_raw,
            'batch_invocations_per_sample': batch,
        }
    values['peak_rss_bytes'] = _rss_limit_bytes()
    values['environment'] = _environment()
    return values


def _ratios(values):
    result = {}
    for role in ('producer', 'verifier'):
        medians = values['candidate'][role]
        result[role] = {
            '400_to_800': medians['800']['median_seconds'] / medians['400']['median_seconds'],
            '800_to_1600': medians['1600']['median_seconds'] / medians['800']['median_seconds'],
        }
    return result


def main():
    if '--single' in sys.argv:
        try:
            affinity = sorted(os.sched_getaffinity(0))
            os.sched_setaffinity(0, {affinity[0]})
        except (AttributeError, OSError, IndexError):
            pass
        print(json.dumps(_single_run(), sort_keys=True))
        return
    clean_runs = []
    for _ in range(CLEAN_RUNS):
        completed = subprocess.run([sys.executable, __file__, '--single'],
                                   check=True, capture_output=True, text=True)
        clean_runs.append(json.loads(completed.stdout))
    report = {'protocol': 'm3-f6-fragmentation-v2', 'clean_runs': clean_runs,
              'ratios': [_ratios(run) for run in clean_runs],
              'contract': {'max_doubling_ratio': 2.8,
                           'max_1600_function_seconds': 90.0,
                           'max_peak_rss_bytes': 1024 * 1024 * 1024}}
    report['pass'] = all(
        ratios[role][step] <= 2.8
        for ratios in report['ratios']
        for role in ('producer', 'verifier')
        for step in ('400_to_800', '800_to_1600')
    ) and all(
        run['candidate'][role]['1600']['median_seconds'] <= 90.0
        for run in clean_runs for role in ('producer', 'verifier')
    ) and all(run['peak_rss_bytes'] <= 1024 * 1024 * 1024 for run in clean_runs)
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report['pass']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
