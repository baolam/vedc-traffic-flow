import pytest
import math
from src.graph.delaunay_builder import haversine


def test_haversine_same_point():
    lat, lon = 10.7769, 106.7009
    dist = haversine(lat, lon, lat, lon)
    assert dist == pytest.approx(0.0, abs=1e-5)


def test_haversine_known_distance():
    # HCM (District 1) to Hanoi approx 1130 - 1150 km
    hcm_lat, hcm_lon = 10.7769, 106.7009
    hn_lat, hn_lon = 21.0285, 105.8542
    dist = haversine(hcm_lat, hcm_lon, hn_lat, hn_lon)
    assert 1100.0 < dist < 1200.0


def test_haversine_short_distance():
    # 0.01 deg lat approx 1.11 km
    dist = haversine(10.0, 106.0, 10.01, 106.0)
    assert 1.0 < dist < 1.2
