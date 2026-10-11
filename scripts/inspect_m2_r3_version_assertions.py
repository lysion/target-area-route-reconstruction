#!/usr/bin/env python3
"""Preflight obsolete M2B/M2C algorithm-version assertions in the PR head.

This is deliberately conservative: it never rewrites an unknown upstream
fixture/schema and it leaves unrelated M2F temporal-overlay 0.1.1 intact.
Run BEFORE CI; investigate every printed version assertion if nonzero.
"""
from __future__ import annotations
import pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
BAD = []
for path in sorted((ROOT / 'tests').rglob('*.py')):
    text = path.read_text()
    for n, line in enumerate(text.splitlines(), 1):
        if not (('version' in line) and ('0.1.2' in line or '0.1.1' in line)):
            continue
        if 'temporal' in line or 'speed_screen' in line or '0.1.1' in line and 'overlay' in line:
            continue
        # QualityAlgorithm bumped 0.1.2 -> 0.1.3, SpatialAlgorithm 0.1.1 -> 0.1.2.
        # Do not infer algorithm provenance solely from an arbitrary variable.
        BAD.append(f'{path.relative_to(ROOT)}:{n}: {line.strip()}')
if BAD:
    print('Review potential obsolete algorithm-version assertions (not necessarily errors):')
    print('\n'.join(BAD))
else:
    print('No potentially outdated quality/spatial-version assertions found.')
# Flag suspicious locations for manual review without conflating M2F v0.1.1.
if BAD:
    sys.exit(2)
