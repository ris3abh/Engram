import math

from engram.decide.calibrate import cross_fit, ece, fit_temperature, reliability, svg_reliability, temper


def test_temper_is_softmax_rescaling():
    p = {"a": 0.7, "b": 0.2, "c": 0.1}
    assert temper(p, 1.0) == {k: temper(p, 1.0)[k] for k in p}
    assert math.isclose(sum(temper(p, 0.5).values()), 1.0)
    assert temper(p, 0.5)["a"] > 0.7 > temper(p, 2.0)["a"]


def test_fit_recovers_sharpening_for_underconfident_backend():
    # Always right but only 60% confident: the fitted temperature sharpens (T < 1) and ECE drops.
    items = [({"yes": 0.6, "no": 0.4}, "yes")] * 40
    t = fit_temperature(items)
    assert t < 0.3
    assert ece(items) > 0.35 and ece(items, t) < 0.05


def test_fit_softens_overconfident_backend():
    items = [({"yes": 0.99, "no": 0.01}, "yes")] * 6 + [({"yes": 0.99, "no": 0.01}, "no")] * 4
    assert fit_temperature(items) > 1.5


def test_reliability_bins_and_cross_fit():
    items = [({"a": 0.95, "b": 0.05}, "a"), ({"a": 0.55, "b": 0.45}, "b")] * 5
    bins = reliability(items)
    assert sum(b.n for b in bins) == 10 and bins[9].n == 5 and bins[5].n == 5
    assert len(cross_fit(items)) == 10
    assert svg_reliability({"x": {"jev": bins}}).startswith("<svg")


def test_no_items():
    assert fit_temperature([]) == 1.0 and ece([]) is None
