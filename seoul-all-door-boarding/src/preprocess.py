import re

import pandas as pd

from .validate import CELL_KEY, nonnegative, require_columns, unique

ID_MAP = {
    '사용년월': 'month', '노선번호': 'route_id', '노선명': 'route_name',
    '표준버스정류장ID': 'stop_id', '버스정류장ARS번호': 'ars_id',
    '역명': 'stop_label', '교통수단타입코드': 'transport_code',
    '교통수단타입명': 'transport_name', '등록일자': 'registered_date',
}


def preprocess(path, encoding='cp949', transport_codes=None):
    raw = pd.read_csv(path, encoding=encoding, dtype=str, keep_default_na=False)
    require_columns(raw, ID_MAP)
    input_rows = len(raw)
    raw = raw.drop_duplicates().copy()
    for col in ID_MAP:
        raw[col] = raw[col].str.strip()
    hourly = {}
    for col in raw:
        match = re.fullmatch(r'(\d{1,2})시(승차|하차)총승객수', col)
        if match:
            key = (int(match[1]), match[2])
            if key in hourly:
                raise ValueError('Duplicate hour column')
            hourly[key] = col
    if set(hourly) != {(h, d) for h in range(24) for d in ['승차', '하차']}:
        raise ValueError('Expected exactly 24 boarding/alighting pairs; review schema')
    nonnegative(raw, list(hourly.values()))
    for col in hourly.values():
        raw[col] = pd.to_numeric(raw[col])
        if (raw[col] % 1 != 0).any():
            raise ValueError('Passenger counts must be integers')
    base = raw.rename(columns=ID_MAP)
    for c in ['month', 'route_id', 'route_name', 'stop_id', 'stop_label', 'transport_code']:
        if base[c].eq('').any():
            raise ValueError(f'Missing identifier: {c}')
    if not base.month.str.fullmatch(r'\d{6}').all():
        raise ValueError('Month must be YYYYMM')
    pd.to_datetime(base['month'], format='%Y%m', errors='raise')
    # The source label carries an apparent sequence suffix; preserve it without assuming its semantics.
    unique(base, CELL_KEY[:-1])
    before_scope = len(base)
    if transport_codes is not None:
        base = base[base.transport_code.isin(transport_codes)]
    if base.empty:
        raise ValueError('No rows remain in the selected scope')
    frames = []
    for hour in range(24):
        block = base[list(ID_MAP.values())].copy()
        block['hour'] = hour
        block['boardings'] = base[hourly[hour, '승차']].astype('int64')
        block['alightings'] = base[hourly[hour, '하차']].astype('int64')
        frames.append(block)
    result = pd.concat(frames, ignore_index=True)
    result['stop_name'] = result.stop_label.str.replace(r'\(\d+\)$', '', regex=True)
    result['days_in_month'] = pd.to_datetime(result.month, format='%Y%m').dt.days_in_month
    result['evidence_type'] = 'observed_monthly_aggregate'
    unique(result, CELL_KEY)
    quality = {
        'input_rows': input_rows, 'exact_duplicates_removed': input_rows - len(raw),
        'rows_excluded_by_scope': before_scope - len(base), 'wide_rows_in_scope': len(base),
        'hourly_cells': len(result), 'missing_by_column': raw.eq('').sum().to_dict(),
        'boarding_total': int(result.boardings.sum()), 'alighting_total': int(result.alightings.sum()),
        'zero_demand_cells': int(((result.boardings + result.alightings) == 0).sum()),
        'coordinates': 'not available; geographic membership not verified',
    }
    return result, quality
