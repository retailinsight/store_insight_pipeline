"""Unit tests for the C8 external API probe response classification.

Run from repo root:
    python -m pytest monitoring/tests/test_api_probe.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api_probe import parse_health

# Shape confirmed with Cornelious 3 Sep 2026
CONFIRMED_BODY = '{"statusCode":200,"status":null,"data":{"status":"ok"}}'


def test_confirmed_healthy_shape_is_ok():
    healthy, detail = parse_health(200, CONFIRMED_BODY)
    assert healthy
    assert 'ok' in detail


def test_non_200_is_fail():
    healthy, detail = parse_health(503, CONFIRMED_BODY)
    assert not healthy
    assert '503' in detail


def test_404_is_fail():
    healthy, _ = parse_health(404, 'Not Found')
    assert not healthy


def test_200_with_bad_data_status_is_fail():
    healthy, detail = parse_health(
        200, '{"statusCode":200,"status":null,"data":{"status":"degraded"}}')
    assert not healthy
    assert 'degraded' in detail


def test_200_with_missing_data_is_fail():
    healthy, _ = parse_health(200, '{"statusCode":200}')
    assert not healthy


def test_200_with_non_json_body_is_fail():
    healthy, detail = parse_health(200, '<html>login page</html>')
    assert not healthy
    assert 'not JSON' in detail
