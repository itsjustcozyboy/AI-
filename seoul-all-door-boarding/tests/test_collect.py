import pytest

from src.collect import register


def test_checksum_pin_rejects_changed_source_before_parsing(tmp_path):
    p = tmp_path / 'source.csv'
    p.write_text('not an official file')
    with pytest.raises(ValueError, match='Source bytes changed'):
        register(p, {'expected_sha256': '0' * 64})
