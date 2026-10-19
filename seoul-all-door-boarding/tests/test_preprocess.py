import pandas as pd
import pytest

from src.preprocess import preprocess
from src.validate import checked_join, validate_coordinates


def source_row():
    # Deliberately synthetic test fixture; never used by the analysis pipeline.
    r = {'사용년월': '202602', '노선번호': '001', '노선명': 'TEST_ONLY',
         '표준버스정류장ID': '000000001', '버스정류장ARS번호': '01001',
         '역명': 'TEST_STOP(00001)', '교통수단타입코드': '010',
         '교통수단타입명': 'TEST_TYPE', '등록일자': '20260303'}
    for h in range(24):
        for d in ['승차', '하차']:
            r[f'{h}시{d}총승객수'] = str(h)
    return r


def test_totals_ids_and_exact_duplicates(tmp_path):
    p = tmp_path / 'fixture.csv'
    pd.DataFrame([source_row(), source_row()]).to_csv(p, encoding='cp949', index=False)
    df, audit = preprocess(p)
    assert len(df) == 24
    assert df.boardings.sum() == sum(range(24))
    assert set(df.ars_id) == {'01001'}
    assert set(df.route_id) == {'001'}
    assert set(df.days_in_month) == {28}
    assert audit['exact_duplicates_removed'] == 1


@pytest.mark.parametrize('bad', ['-1', '', 'nan', 'inf', '1.5'])
def test_invalid_counts_rejected(tmp_path, bad):
    row = source_row(); row['1시승차총승객수'] = bad
    p = tmp_path / 'fixture.csv'
    pd.DataFrame([row]).to_csv(p, encoding='cp949', index=False)
    with pytest.raises(ValueError):
        preprocess(p)


def test_conflicting_duplicate_not_silently_summed(tmp_path):
    a = source_row(); b = source_row(); b['1시승차총승객수'] = '999'
    p = tmp_path / 'fixture.csv'
    pd.DataFrame([a, b]).to_csv(p, encoding='cp949', index=False)
    with pytest.raises(ValueError, match='Ambiguous'):
        preprocess(p)


def test_different_stop_occurrences_preserved(tmp_path):
    a = source_row(); b = source_row(); b['역명'] = 'TEST_STOP(00050)'
    p = tmp_path / 'fixture.csv'
    pd.DataFrame([a, b]).to_csv(p, encoding='cp949', index=False)
    df, _ = preprocess(p)
    assert len(df) == 48


def test_join_rejects_many_to_many():
    x = pd.DataFrame({'stop_id': ['1', '1']})
    with pytest.raises(ValueError):
        checked_join(x, x, ['stop_id'])


def test_coordinate_ranges():
    x = pd.DataFrame({'stop_id': ['1'], 'longitude': [37.5], 'latitude': [127.0]})
    with pytest.raises(ValueError):
        validate_coordinates(x)
