"""F8 -- the go/no-go memo claimed four conditions but only checked two.
decision_stage() now enforces the staged pipeline PAPER -> TESTNET -> LIVE."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from cockpit import decision_stage  # noqa: E402


def test_synthetic_never_decision_grade():
    stage, line = decision_stage(gate=True, synthetic=True, paper_days=999,
                                 recon={"n_with_observed_costs": 99,
                                        "within_kill_criterion": True})
    assert stage == "DEMO" and "NO-GO" in line


def test_gate_fail_blocks_everything():
    stage, line = decision_stage(gate=False, synthetic=False, paper_days=999,
                                 recon={"n_with_observed_costs": 0})
    assert stage == "PAPER" and "NO-GO" in line and "retune" in line


def test_paper_clock_incomplete():
    stage, line = decision_stage(gate=True, synthetic=False, paper_days=7,
                                 recon={"n_with_observed_costs": 0})
    assert stage == "PAPER" and "7/20" in line


def test_paper_complete_goes_to_testnet_not_live():
    stage, line = decision_stage(gate=True, synthetic=False, paper_days=25,
                                 recon={"n_with_observed_costs": 0})
    assert stage == "TESTNET" and "GO to TESTNET" in line and "live still blocked" in line


def test_testnet_costs_within_bounds_unlocks_live():
    stage, line = decision_stage(gate=True, synthetic=False, paper_days=25,
                                 recon={"n_with_observed_costs": 12,
                                        "within_kill_criterion": True})
    assert stage == "LIVE" and "10% of target size" in line


def test_testnet_costs_exceeding_kill_criterion_blocks_live():
    stage, line = decision_stage(gate=True, synthetic=False, paper_days=25,
                                 recon={"n_with_observed_costs": 12,
                                        "within_kill_criterion": False})
    assert stage == "TESTNET" and "kill criterion" in line


def test_one_fill_is_not_enough_for_live():
    # A single trivial fill (e.g. flattening pre-funded testnet balances)
    # must NOT unlock LIVE -- evidence accumulates to MIN_OBSERVED_FILLS.
    stage, line = decision_stage(gate=True, synthetic=False, paper_days=25,
                                 recon={"n_with_observed_costs": 1,
                                        "within_kill_criterion": True})
    assert stage == "TESTNET" and "1/5 observed fills" in line
