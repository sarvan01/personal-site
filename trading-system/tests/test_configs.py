from trading_system.config import CONFIGS, DEFAULT, H1B


def test_h1_registration_is_untouched():
    # The original H1 registration must stay auditable: 3-lookback grid,
    # 0.5% per-trade risk, BTC/ETH universe.
    assert DEFAULT.trend.lookbacks == (50, 100, 200)
    assert DEFAULT.risk.per_trade_risk == 0.005
    assert DEFAULT.universe == ("BTCUSDT", "ETHUSDT")


def test_h1b_is_a_separate_config():
    assert CONFIGS["h1b"] is H1B
    assert CONFIGS["default"] is DEFAULT
    assert H1B.trend.lookbacks == (50, 100)
    assert H1B.risk.per_trade_risk == 0.01
    assert H1B.universe == ("BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT")
    # Everything not explicitly amended stays identical to the registration.
    assert H1B.risk.dd_go_flat == DEFAULT.risk.dd_go_flat
    assert H1B.costs == DEFAULT.costs
    assert H1B.carry == DEFAULT.carry
