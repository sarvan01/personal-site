import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trading_system.data import synthetic_funding, synthetic_klines


@pytest.fixture(scope="session")
def btc():
    return synthetic_klines(days=1500, seed=7)


@pytest.fixture(scope="session")
def eth():
    return synthetic_klines(days=1500, seed=13)


@pytest.fixture(scope="session")
def funding():
    return synthetic_funding(days=600, seed=11)
