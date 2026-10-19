"""Fail closed on ambiguous keys and impossible quantities."""
import numpy as np
import pandas as pd

CELL_KEY = ['month', 'route_id', 'route_name', 'stop_id', 'stop_label', 'transport_code', 'hour']


def require_columns(df, names):
    missing = sorted(set(names) - set(df.columns))
    if missing:
        raise ValueError(f'Missing columns: {missing}')


def nonnegative(df, columns):
    for name in columns:
        values = pd.to_numeric(df[name], errors='raise')
        if not np.isfinite(values).all() or (values < 0).any():
            raise ValueError(f'{name}: missing, infinite or negative values')


def unique(df, keys):
    if df.duplicated(keys).any():
        raise ValueError(f'Ambiguous duplicate key: {keys}')


def validate_coordinates(df):
    require_columns(df, ['stop_id', 'longitude', 'latitude'])
    unique(df, ['stop_id'])
    lon, lat = pd.to_numeric(df.longitude), pd.to_numeric(df.latitude)
    if not (lon.between(-180, 180) & lat.between(-90, 90)).all():
        raise ValueError('Invalid WGS84 coordinates')
    return df.assign(outside_seoul_region=~(lon.between(126, 128) & lat.between(36.5, 38.5)))


def checked_join(left, right, keys):
    """Only same-grain aggregates or unique lookup tables; never raw events to monthly totals."""
    unique(right, keys)
    return left.merge(right, on=keys, how='left', validate='many_to_one', indicator=True)
