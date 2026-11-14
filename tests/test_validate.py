"""Tratamento de dados ausentes."""

import numpy as np

from data.validate import fill_gaps, quality_report


def test_short_temperature_gap_is_interpolated_and_flagged(raw):
    broken = raw.copy()
    broken.loc["1995-01-10":"1995-01-12", "tmax_c"] = np.nan
    fixed = fill_gaps(broken)
    assert fixed.loc["1995-01-10":"1995-01-12", "tmax_c"].notna().all()
    low, high = sorted([raw.loc["1995-01-09", "tmax_c"], raw.loc["1995-01-13", "tmax_c"]])
    assert fixed.loc["1995-01-11", "tmax_c"] >= low and fixed.loc["1995-01-11", "tmax_c"] <= high
    assert (fixed.loc["1995-01-10":"1995-01-12", "qc_flag"] == 1).all()
    assert fixed["qc_flag"].sum() == 3
    assert broken.loc["1995-01-11", "tmax_c"] != broken.loc["1995-01-11", "tmax_c"]   # NaN intacto


def test_long_gap_stays_missing(raw):
    broken = raw.copy()
    broken.loc["1995-01-01":"1995-01-20", "tmin_c"] = np.nan
    fixed = fill_gaps(broken, max_gap_days=5)
    assert fixed.loc["1995-01-10", "tmin_c"] != fixed.loc["1995-01-10", "tmin_c"]


def test_rain_gap_uses_day_of_year_mean_not_interpolation(raw):
    broken = raw.copy()
    broken.loc["1995-01-15", "p_mm"] = np.nan
    fixed = fill_gaps(broken)
    others = raw[(raw.index.dayofyear == 15) & (raw.index.year != 1995)]["p_mm"]
    assert abs(fixed.loc["1995-01-15", "p_mm"] - others.mean()) < 1e-9
    assert fixed.loc["1995-01-15", "qc_flag"] == 1


def test_missing_calendar_days_are_restored(raw):
    broken = raw.drop(raw.loc["1996-03-05":"1996-03-06"].index)
    assert quality_report(broken)["calendar_gaps"] == 2
    fixed = fill_gaps(broken)
    assert len(fixed) == len(raw)
    assert fixed.loc["1996-03-05", "source"] == "SINTÉTICO"
    assert fixed.loc["1996-03-05", "tmax_c"] == fixed.loc["1996-03-05", "tmax_c"]


def test_out_of_range_values_are_treated_as_missing(raw):
    broken = raw.copy()
    broken.loc["1997-02-01", "p_mm"] = -5.0
    broken.loc["1997-02-02", "tmax_c"] = 99.0
    report = quality_report(broken)
    assert report["out_of_range"] == 2
    fixed = fill_gaps(broken)
    assert fixed.loc["1997-02-01", "p_mm"] >= 0
    assert fixed.loc["1997-02-02", "tmax_c"] < 60


def test_quality_report_on_clean_data(raw):
    report = quality_report(raw)
    assert report["days"] == len(raw) and report["calendar_gaps"] == 0
    assert report["missing_fraction"] == {"p_mm": 0.0, "tmax_c": 0.0, "tmin_c": 0.0}
    assert report["out_of_range"] == 0 and report["tmin_above_tmax"] == 0
    assert (report["start"], report["end"]) == ("1990-01-01", "2002-12-31")
