"""Download the verified official CSV, preserve bytes and acquisition evidence."""
import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from .common import ROOT, config, digest, write_json


def register(path, source, acquisition='download', http_status=None):
    checksum = digest(path)
    if source.get('expected_sha256') and checksum != source['expected_sha256']:
        raise ValueError('Source bytes changed from the verified snapshot; investigate before updating the pin')
    frame = pd.read_csv(path, encoding=source['encoding'], dtype=str)
    if '사용년월' not in frame or set(frame['사용년월']) != {source['month']}:
        raise ValueError('Downloaded file does not match the configured month/schema')
    manifest = {
        **source, 'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
        'acquisition': acquisition, 'http_status': http_status,
        'sha256': checksum, 'bytes': Path(path).stat().st_size,
        'rows': len(frame), 'columns': list(frame),
        'storage_types': {c: 'CSV text (loaded as string)' for c in frame},
        'observed_months': sorted(frame['사용년월'].unique().tolist()),
    }
    write_json(str(path) + '.manifest.json', manifest)
    return manifest


def collect(register_existing=False):
    source = config('settings.yaml')['source']
    path = ROOT / source['raw_file']
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(str(path) + '.manifest.json')
    if path.exists():
        if manifest_path.exists():
            import json
            saved = json.loads(manifest_path.read_text())
            if digest(path) != saved['sha256']:
                raise ValueError('Raw file checksum changed; preserve and investigate')
            if saved['month'] != source['month'] or saved['dataset_id'] != source['dataset_id']:
                raise ValueError('Configured source differs from the recorded acquisition')
            if source.get('expected_sha256') and saved['sha256'] != source['expected_sha256']:
                raise ValueError('Recorded source differs from the pinned checksum')
            return saved
        if not register_existing:
            raise FileExistsError('Use --register-existing for a manually downloaded official file')
        return register(path, source, 'manual_download_registered')
    response = requests.post(source['download_url'], data=source['form'], timeout=(15, 120))
    response.raise_for_status()
    temp = path.with_suffix('.part')
    temp.write_bytes(response.content)
    try:
        pd.read_csv(temp, encoding=source['encoding'], nrows=2)
        result = register(temp, source, http_status=response.status_code)
        temp.rename(path)
        Path(str(temp) + '.manifest.json').rename(manifest_path)
    except Exception:
        temp.unlink(missing_ok=True)
        Path(str(temp) + '.manifest.json').unlink(missing_ok=True)
        raise
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--register-existing', action='store_true')
    args = parser.parse_args()
    print(collect(args.register_existing)['sha256'])
