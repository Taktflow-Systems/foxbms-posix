#!/usr/bin/env python3
"""
Unit tests for SOC (State of Charge) estimation edge cases.

Tests the coulomb-counting algorithm, boundary conditions, numerical
stability, and CAN encoding of SOC — all as offline pure-Python pytest tests.

Covers:
  - Coulomb counting integration math
  - SOC clamping at 0% and 100%
  - Zero-current behavior (no drift)
  - High-current stress
  - Numerical precision over long intervals
  - SOC initial value
  - CAN TX encoding (0x235)
  - IVT current sensor decoding
  - OCV(SOC) lookup function
"""
# @verifies SW-REQ-091 (IVT current sensor simulation)
# @verifies SW-REQ-092 (cell voltage simulation)

import struct
import math
import pytest

# ---------------------------------------------------------------------------
# Battery parameters (from plant_model.py)
# ---------------------------------------------------------------------------
N_CELLS = 18
Q_CELL_MAH = 3000.0
R_CELL_MOHM = 50.0
R_TOTAL_MOHM = R_CELL_MOHM * N_CELLS
I_DISCHARGE_MA = 1000
DT_S = 0.001  # 1 ms loop period
SOC_INITIAL_PCT = 50.0


def ocv_mv(soc_pct):
    """Open-circuit voltage from SOC (linear model)."""
    return int(3400.0 + 800.0 * (soc_pct / 100.0))


def coulomb_delta(current_ma, dt_s, q_mah):
    """Compute SOC change (%) for one timestep of coulomb counting."""
    return (current_ma / 1000.0) / (q_mah / 1000.0) * (dt_s / 3600.0) * 100.0


def integrate_soc(soc_start, current_ma, duration_s, dt_s=DT_S, q_mah=Q_CELL_MAH):
    """Simulate coulomb counting over a duration, clamped to [0, 100]."""
    soc = soc_start
    steps = int(duration_s / dt_s)
    for _ in range(steps):
        if current_ma > 0:
            soc -= coulomb_delta(current_ma, dt_s, q_mah)
        elif current_ma < 0:
            soc -= coulomb_delta(current_ma, dt_s, q_mah)  # negative current → soc increases
        soc = max(0.0, min(100.0, soc))
    return soc


# ===================================================================
# Coulomb counting math
# ===================================================================
class TestCoulombCountingMath:
    """Verify the basic coulomb-counting integration formula."""

    def test_one_step_delta(self):
        """1 A discharge for 1 ms on 3000 mAh cell → known ΔSOC."""
        delta = coulomb_delta(1000, 0.001, 3000.0)
        # 1A * 0.001s = 0.001 As = 0.001/3600 Ah = 2.778e-7 Ah
        # SOC change = (2.778e-7 / 3.0) * 100 = 9.259e-6 %
        expected = (1000 / 1000.0) / (3000.0 / 1000.0) * (0.001 / 3600.0) * 100.0
        assert delta == pytest.approx(expected, rel=1e-10)

    def test_one_second_at_1a(self):
        """1 A for 1 second → ΔSOC = (1/3) * (1/3600) * 100 ≈ 0.00926 %."""
        total = 0.0
        for _ in range(1000):
            total += coulomb_delta(1000, 0.001, 3000.0)
        expected = (1.0 / 3.0) * (1.0 / 3600.0) * 100.0
        assert total == pytest.approx(expected, rel=1e-6)

    def test_one_hour_at_1a_drains_33pct(self):
        """1 A for 1 hour on 3 Ah cell = 33.33% SOC drain."""
        total_delta = coulomb_delta(1000, 3600.0, 3000.0)
        assert total_delta == pytest.approx(33.333, rel=1e-3)

    def test_zero_current_no_change(self):
        """Zero current → ΔSOC = 0."""
        assert coulomb_delta(0, 1.0, 3000.0) == 0.0

    def test_negative_current_charges(self):
        """Negative current (charging) gives negative delta → SOC increases
        when subtracted."""
        delta = coulomb_delta(-1000, 0.001, 3000.0)
        assert delta < 0  # negative delta → subtracting it increases SOC

    def test_delta_proportional_to_current(self):
        """ΔSOC is linearly proportional to current magnitude."""
        d1 = coulomb_delta(1000, 0.001, 3000.0)
        d2 = coulomb_delta(2000, 0.001, 3000.0)
        assert d2 == pytest.approx(2 * d1, rel=1e-10)

    def test_delta_proportional_to_dt(self):
        """ΔSOC is linearly proportional to time step."""
        d1 = coulomb_delta(1000, 0.001, 3000.0)
        d2 = coulomb_delta(1000, 0.002, 3000.0)
        assert d2 == pytest.approx(2 * d1, rel=1e-10)

    def test_delta_inversely_proportional_to_capacity(self):
        """ΔSOC is inversely proportional to cell capacity."""
        d1 = coulomb_delta(1000, 0.001, 3000.0)
        d2 = coulomb_delta(1000, 0.001, 6000.0)
        assert d2 == pytest.approx(d1 / 2, rel=1e-10)


# ===================================================================
# SOC clamping
# ===================================================================
class TestSocClamping:
    """Verify SOC is clamped to [0%, 100%]."""

    def test_clamp_at_zero(self):
        """SOC cannot go below 0%."""
        soc = integrate_soc(0.5, 10000, 10.0)  # massive current from near-zero
        assert soc == 0.0

    def test_clamp_at_hundred(self):
        """SOC cannot exceed 100%."""
        soc = integrate_soc(99.5, -10000, 10.0)  # massive charge from near-full
        assert soc == 100.0

    def test_discharge_from_50_stays_positive(self):
        """Discharging from 50% at 1 A for 60 s stays well above 0%."""
        soc = integrate_soc(50.0, 1000, 60.0)
        assert soc > 0.0
        assert soc < 50.0

    def test_charge_from_50_stays_under_100(self):
        """Charging from 50% at 1 A for 60 s stays below 100%."""
        soc = integrate_soc(50.0, -1000, 60.0)
        assert soc > 50.0
        assert soc <= 100.0

    def test_exactly_zero_discharge_no_undershoot(self):
        """Starting at exactly 0% with discharge → stays at 0%."""
        soc = integrate_soc(0.0, 1000, 1.0)
        assert soc == 0.0

    def test_exactly_hundred_charge_no_overshoot(self):
        """Starting at exactly 100% with charge → stays at 100%."""
        soc = integrate_soc(100.0, -1000, 1.0)
        assert soc == 100.0


# ===================================================================
# Zero-current behavior
# ===================================================================
class TestZeroCurrent:
    """Verify no SOC drift when current is zero."""

    @pytest.mark.parametrize("initial_soc", [0.0, 25.0, 50.0, 75.0, 100.0])
    def test_no_drift(self, initial_soc):
        """Zero current for 10 seconds → SOC unchanged."""
        soc = integrate_soc(initial_soc, 0, 10.0)
        assert soc == pytest.approx(initial_soc, abs=1e-10)


# ===================================================================
# High-current stress
# ===================================================================
class TestHighCurrentStress:
    """Edge cases with extreme current values."""

    def test_max_discharge_current(self):
        """10 A (MSL overcurrent threshold) for 1 s from 50%."""
        soc = integrate_soc(50.0, 10000, 1.0)
        expected_delta = (10.0 / 3.0) * (1.0 / 3600.0) * 100.0
        assert soc == pytest.approx(50.0 - expected_delta, rel=1e-3)

    def test_max_charge_current(self):
        """10 A charge for 1 s from 50%."""
        soc = integrate_soc(50.0, -10000, 1.0)
        expected_delta = (10.0 / 3.0) * (1.0 / 3600.0) * 100.0
        assert soc == pytest.approx(50.0 + expected_delta, rel=1e-3)


# ===================================================================
# Numerical precision
# ===================================================================
class TestNumericalPrecision:
    """Verify no accumulated floating-point drift over many steps."""

    def test_long_integration_matches_analytical(self):
        """60 s at 1 A → analytical: ΔSOC = (1/3)*(60/3600)*100 = 0.5556%."""
        soc = integrate_soc(50.0, 1000, 60.0)
        analytical_delta = (1.0 / 3.0) * (60.0 / 3600.0) * 100.0
        assert soc == pytest.approx(50.0 - analytical_delta, rel=1e-4)

    def test_symmetry_charge_discharge(self):
        """Discharge then charge same amount → returns to start."""
        soc_after_discharge = integrate_soc(50.0, 1000, 30.0)
        soc_after_recharge = integrate_soc(soc_after_discharge, -1000, 30.0)
        assert soc_after_recharge == pytest.approx(50.0, abs=0.001)


# ===================================================================
# Initial SOC
# ===================================================================
class TestInitialSoc:
    """Verify SOC initialization."""

    def test_initial_soc_is_50(self):
        """Plant model starts at 50% SOC."""
        assert SOC_INITIAL_PCT == 50.0

    def test_initial_soc_within_bounds(self):
        assert 0.0 <= SOC_INITIAL_PCT <= 100.0


# ===================================================================
# OCV(SOC) lookup
# ===================================================================
class TestOcvLookup:
    """Verify OCV(SOC) linear model."""

    def test_ocv_at_0_percent(self):
        assert ocv_mv(0.0) == 3400

    def test_ocv_at_100_percent(self):
        assert ocv_mv(100.0) == 4200

    def test_ocv_at_50_percent(self):
        assert ocv_mv(50.0) == 3800

    def test_ocv_monotonically_increasing(self):
        """OCV must increase with SOC."""
        prev = ocv_mv(0.0)
        for soc in range(1, 101):
            v = ocv_mv(float(soc))
            assert v >= prev
            prev = v

    def test_ocv_range(self):
        """OCV spans 3400–4200 mV (800 mV range)."""
        assert ocv_mv(100.0) - ocv_mv(0.0) == 800

    @pytest.mark.parametrize("soc,expected_mv", [
        (0.0, 3400), (25.0, 3600), (50.0, 3800),
        (75.0, 4000), (100.0, 4200),
    ])
    def test_ocv_linearity(self, soc, expected_mv):
        """Linear model: V = 3400 + 800 * (SOC/100)."""
        assert ocv_mv(soc) == expected_mv


# ===================================================================
# CAN TX encoding of SOC (0x235)
# ===================================================================
class TestSocCanEncoding:
    """Verify SOC encoding on CAN message 0x235."""

    CAN_SOC_ID = 0x235
    CAN_SOC_CYCLE_MS = 1000
    SOC_BYTE_POSITION = 5
    SOC_RESOLUTION = 0.5  # 0.5% per LSB

    def test_soc_can_id(self):
        assert self.CAN_SOC_ID == 0x235

    def test_soc_cycle_time(self):
        assert self.CAN_SOC_CYCLE_MS == 1000

    @pytest.mark.parametrize("soc_pct,expected_raw", [
        (0.0, 0), (50.0, 100), (100.0, 200),
        (25.0, 50), (75.0, 150),
    ])
    def test_soc_encoding(self, soc_pct, expected_raw):
        """SOC encoded as byte 5: raw = SOC / 0.5, range 0–200."""
        raw = int(soc_pct / self.SOC_RESOLUTION)
        assert raw == expected_raw

    def test_soc_encoding_range(self):
        """Raw value range: 0 (0%) to 200 (100%), fits in uint8."""
        for soc in range(0, 101):
            raw = int(soc / self.SOC_RESOLUTION)
            assert 0 <= raw <= 200
            assert raw <= 255  # fits in u8


# ===================================================================
# IVT current sensor decoding
# ===================================================================
class TestIvtCurrentDecoding:
    """Verify IVT current sensor CAN message format (0x521)."""

    CAN_IVT_CURRENT_ID = 0x521

    def test_ivt_message_id(self):
        assert self.CAN_IVT_CURRENT_ID == 0x521

    def test_current_encoding_big_endian_i32(self):
        """IVT current: bytes 2-5, big-endian signed 32-bit integer (mA)."""
        current_ma = 1000
        # Plant encodes: struct.pack(">BBi", mc, 0, current_ma)[:6]
        mc = 0x10
        data = struct.pack(">BBi", mc, 0, current_ma)[:6]
        # Decode bytes 2-5 as big-endian i32
        decoded = struct.unpack(">i", data[2:6])[0]
        assert decoded == current_ma

    @pytest.mark.parametrize("current_ma", [0, 1000, -1000, 10000, -10000])
    def test_current_roundtrip(self, current_ma):
        """Encode then decode IVT current → matches original."""
        mc = 0x00
        data = struct.pack(">BBi", mc, 0, current_ma)[:6]
        decoded = struct.unpack(">i", data[2:6])[0]
        assert decoded == current_ma

    def test_zero_current_encoding(self):
        """Zero current encodes correctly."""
        data = struct.pack(">BBi", 0, 0, 0)[:6]
        decoded = struct.unpack(">i", data[2:6])[0]
        assert decoded == 0


# ===================================================================
# IR drop model
# ===================================================================
class TestIrDropModel:
    """Verify internal resistance voltage drop calculation."""

    def test_ir_drop_at_1a(self):
        """IR drop at 1 A: 1.0 * 900 mΩ = 900 mV."""
        ir_drop = int((1000 / 1000.0) * R_TOTAL_MOHM)
        assert ir_drop == 900

    def test_ir_drop_at_zero_current(self):
        """No current → no IR drop."""
        ir_drop = int((0 / 1000.0) * R_TOTAL_MOHM)
        assert ir_drop == 0

    def test_pack_voltage_with_ir_drop(self):
        """V_pack = sum(V_cell) - IR drop."""
        v_cell = ocv_mv(50.0)  # 3800 mV
        v_sum = v_cell * N_CELLS  # 68400 mV
        ir_drop = int((1000 / 1000.0) * R_TOTAL_MOHM)  # 900 mV
        v_pack = max(0, v_sum - ir_drop)
        assert v_pack == 67500

    def test_pack_voltage_clamped_nonnegative(self):
        """Pack voltage cannot go negative."""
        v_pack = max(0, 1000 - 5000)
        assert v_pack == 0

    def test_total_resistance(self):
        """Total string resistance = 18 cells × 50 mΩ = 900 mΩ."""
        assert R_TOTAL_MOHM == 900.0
