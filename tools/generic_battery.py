#!/usr/bin/env python3
"""Generic electro-thermal battery model.

The model is intentionally low-order and simulation-friendly:

* OCV(SOC) lookup table for a configurable generic cell.
* Two-RC equivalent circuit for fast and slow polarization.
* Coulomb-counted SOC with simple temperature capacity derating.
* Lumped thermal state using irreversible electrical heat and Newton cooling.
* Cell-to-cell spread plus AFE-style moving average for measured voltages.

Current sign convention follows the referenced plant-model convention:
positive current discharges the string, negative current charges it.
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from dataclasses import dataclass, replace
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


LookupPoints = Tuple[Tuple[float, float], ...]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def interpolate(points: LookupPoints, x_value: float) -> float:
    """Piecewise-linear lookup with endpoint clamping."""
    if not points:
        raise ValueError("lookup table must contain at least one point")
    if x_value <= points[0][0]:
        return points[0][1]
    if x_value >= points[-1][0]:
        return points[-1][1]
    for index in range(len(points) - 1):
        x0, y0 = points[index]
        x1, y1 = points[index + 1]
        if x0 <= x_value <= x1:
            if x1 == x0:
                return y0
            fraction = (x_value - x0) / (x1 - x0)
            return y0 + fraction * (y1 - y0)
    return points[-1][1]


def table_slope(points: LookupPoints, x_value: float) -> float:
    """Return local dY/dX slope for a piecewise-linear table."""
    if len(points) < 2:
        return 0.0
    x_value = _clamp(x_value, points[0][0], points[-1][0])
    for index in range(len(points) - 1):
        x0, y0 = points[index]
        x1, y1 = points[index + 1]
        if x0 <= x_value <= x1:
            if x1 == x0:
                return 0.0
            return (y1 - y0) / (x1 - x0)
    x0, y0 = points[-2]
    x1, y1 = points[-1]
    return (y1 - y0) / (x1 - x0)


# SOC is fraction [0..1], voltage is V. This default curve represents a
# high-voltage large-format cell class using public proxy data.
GENERIC_OCV_TABLE: LookupPoints = (
    (0.00, 2.85),
    (0.05, 3.12),
    (0.10, 3.30),
    (0.20, 3.45),
    (0.30, 3.53),
    (0.40, 3.60),
    (0.50, 3.66),
    (0.60, 3.75),
    (0.70, 3.88),
    (0.80, 4.04),
    (0.90, 4.20),
    (0.95, 4.27),
    (1.00, 4.30),
)


LOW_VOLTAGE_OCV_TABLE: LookupPoints = (
    (0.00, 2.50),
    (0.05, 3.00),
    (0.10, 3.15),
    (0.20, 3.24),
    (0.30, 3.28),
    (0.40, 3.30),
    (0.50, 3.31),
    (0.60, 3.32),
    (0.70, 3.33),
    (0.80, 3.34),
    (0.90, 3.40),
    (0.95, 3.50),
    (1.00, 3.65),
)


# Temperature tables are intentionally smooth and conservative.
# Temperature is degC. Values are dimensionless multipliers.
CAPACITY_TEMP_SCALE: LookupPoints = (
    (-30.0, 0.55),
    (-20.0, 0.70),
    (0.0, 0.86),
    (25.0, 1.00),
    (45.0, 0.97),
    (55.0, 0.95),
    (65.0, 0.90),
)

RESISTANCE_TEMP_SCALE: LookupPoints = (
    (-30.0, 4.80),
    (-20.0, 3.20),
    (0.0, 1.80),
    (25.0, 1.00),
    (45.0, 0.85),
    (55.0, 0.95),
    (65.0, 1.05),
)

RESISTANCE_SOC_SCALE: LookupPoints = (
    (0.00, 1.60),
    (0.10, 1.25),
    (0.20, 1.08),
    (0.50, 1.00),
    (0.80, 1.04),
    (0.90, 1.12),
    (1.00, 1.30),
)

# Optional entropic heat approximation, V/K. Zero-centered and small because
# this model is meant for BMS SIL behavior, not calorimetry.
ENTROPIC_COEFF_V_PER_K: LookupPoints = (
    (0.00, -0.00005),
    (0.20, -0.00002),
    (0.50, 0.00000),
    (0.80, 0.00002),
    (1.00, 0.00004),
)


@dataclass(frozen=True)
class CellParameters:
    """Nominal parameters for a configurable generic cell."""

    capacity_ah: float = 100.0
    ocv_table: LookupPoints = GENERIC_OCV_TABLE
    min_voltage_v: float = 2.50
    max_voltage_v: float = 4.30
    r0_ohm: float = 0.00055
    r1_ohm: float = 0.00012
    tau1_s: float = 5.0
    r2_ohm: float = 0.00023
    tau2_s: float = 300.0
    hysteresis_max_v: float = 0.015
    hysteresis_tau_s: float = 1800.0
    coulombic_efficiency_charge: float = 0.995
    coulombic_efficiency_discharge: float = 1.0
    thermal_capacity_j_per_k: float = 3000.0
    cooling_w_per_k: float = 4.0
    recommended_soc_min: float = 0.10
    recommended_soc_max: float = 0.90
    continuous_charge_c: float = 3.0
    continuous_discharge_c: float = 4.0
    pulse_charge_c: float = 4.0
    pulse_discharge_c: float = 6.0
    charge_temperature_min_c: float = 0.0
    charge_temperature_max_c: float = 55.0
    discharge_temperature_min_c: float = -20.0
    discharge_temperature_max_c: float = 55.0
    ocv_offset_v: float = 0.0
    manufacturing_capacity_scale: float = 1.0
    manufacturing_resistance_scale: float = 1.0
    thermal_capacity_scale: float = 1.0

    def ocv_v(self, soc: float) -> float:
        return interpolate(self.ocv_table, _clamp(soc, 0.0, 1.0)) + self.ocv_offset_v

    def d_ocv_d_soc(self, soc: float) -> float:
        return table_slope(self.ocv_table, _clamp(soc, 0.0, 1.0))

    def effective_capacity_ah(self, temperature_c: float, soh_capacity: float) -> float:
        return (
            self.capacity_ah
            * self.manufacturing_capacity_scale
            * soh_capacity
            * interpolate(CAPACITY_TEMP_SCALE, temperature_c)
        )

    def effective_resistance_scale(self, soc: float, temperature_c: float, soh_resistance: float) -> float:
        return (
            self.manufacturing_resistance_scale
            * soh_resistance
            * interpolate(RESISTANCE_TEMP_SCALE, temperature_c)
            * interpolate(RESISTANCE_SOC_SCALE, _clamp(soc, 0.0, 1.0))
        )

    def effective_resistances(self, soc: float, temperature_c: float, soh_resistance: float) -> Tuple[float, float, float]:
        scale = self.effective_resistance_scale(soc, temperature_c, soh_resistance)
        return self.r0_ohm * scale, self.r1_ohm * scale, self.r2_ohm * scale

    def effective_thermal_capacity_j_per_k(self) -> float:
        return self.thermal_capacity_j_per_k * self.thermal_capacity_scale

    def current_limits_a(self) -> Dict[str, float]:
        return {
            "continuous_charge_a": self.capacity_ah * self.continuous_charge_c,
            "continuous_discharge_a": self.capacity_ah * self.continuous_discharge_c,
            "pulse_charge_a": self.capacity_ah * self.pulse_charge_c,
            "pulse_discharge_a": self.capacity_ah * self.pulse_discharge_c,
        }


def make_cell_parameters(profile: str = "high-voltage", capacity_ah: float = 100.0) -> CellParameters:
    """Create generic cell parameters from a public-proxy profile."""
    if profile == "high-voltage":
        return CellParameters(capacity_ah=capacity_ah)
    if profile == "low-voltage":
        return CellParameters(
            capacity_ah=capacity_ah,
            ocv_table=LOW_VOLTAGE_OCV_TABLE,
            min_voltage_v=2.50,
            max_voltage_v=3.65,
            r0_ohm=0.00065,
            r1_ohm=0.00015,
            r2_ohm=0.00025,
            thermal_capacity_j_per_k=1900.0,
            continuous_charge_c=1.0,
            continuous_discharge_c=1.0,
            pulse_charge_c=1.0,
            pulse_discharge_c=3.0,
        )
    raise ValueError(f"unsupported profile: {profile}")


@dataclass
class CellState:
    soc: float = 0.50
    temperature_c: float = 25.0
    v_rc1: float = 0.0
    v_rc2: float = 0.0
    hysteresis_v: float = 0.0
    soh_capacity: float = 1.0
    soh_resistance: float = 1.0


@dataclass(frozen=True)
class CellOutput:
    soc: float
    ocv_v: float
    terminal_voltage_v: float
    temperature_c: float
    heat_w: float
    r0_ohm: float
    r1_ohm: float
    r2_ohm: float
    v_rc1: float
    v_rc2: float
    hysteresis_v: float


class CellModel:
    """Single-cell second-order ECM plus lumped thermal model."""

    def __init__(self, parameters: Optional[CellParameters] = None, state: Optional[CellState] = None) -> None:
        self.parameters = parameters or CellParameters()
        self.state = state or CellState()

    def step(self, current_a: float, dt_s: float, ambient_c: float = 25.0) -> CellOutput:
        if dt_s <= 0.0:
            raise ValueError("dt_s must be positive")

        p = self.parameters
        s = self.state
        capacity_ah = max(1e-9, p.effective_capacity_ah(s.temperature_c, s.soh_capacity))

        if current_a >= 0.0:
            delta_ah = current_a * dt_s / 3600.0 / p.coulombic_efficiency_discharge
        else:
            delta_ah = current_a * dt_s / 3600.0 * p.coulombic_efficiency_charge
        s.soc = _clamp(s.soc - (delta_ah / capacity_ah), 0.0, 1.0)

        r0, r1, r2 = p.effective_resistances(s.soc, s.temperature_c, s.soh_resistance)
        s.v_rc1 = self._advance_rc_voltage(s.v_rc1, current_a, r1, p.tau1_s, dt_s)
        s.v_rc2 = self._advance_rc_voltage(s.v_rc2, current_a, r2, p.tau2_s, dt_s)
        s.hysteresis_v = self._advance_hysteresis(s.hysteresis_v, current_a, p, dt_s)

        ocv = p.ocv_v(s.soc)
        terminal = ocv - current_a * r0 - s.v_rc1 - s.v_rc2 - s.hysteresis_v
        heat_w = self._heat_generation_w(current_a, ocv, terminal, s.temperature_c, s.soc)

        thermal_capacity = max(1e-9, p.effective_thermal_capacity_j_per_k())
        cooling_w = p.cooling_w_per_k * (s.temperature_c - ambient_c)
        s.temperature_c += (heat_w - cooling_w) * dt_s / thermal_capacity

        return CellOutput(
            soc=s.soc,
            ocv_v=ocv,
            terminal_voltage_v=terminal,
            temperature_c=s.temperature_c,
            heat_w=heat_w,
            r0_ohm=r0,
            r1_ohm=r1,
            r2_ohm=r2,
            v_rc1=s.v_rc1,
            v_rc2=s.v_rc2,
            hysteresis_v=s.hysteresis_v,
        )

    @staticmethod
    def _advance_rc_voltage(previous_v: float, current_a: float, resistance_ohm: float, tau_s: float, dt_s: float) -> float:
        if tau_s <= 0.0:
            return current_a * resistance_ohm
        alpha = math.exp(-dt_s / tau_s)
        return alpha * previous_v + (1.0 - alpha) * current_a * resistance_ohm

    @staticmethod
    def _advance_hysteresis(previous_v: float, current_a: float, parameters: CellParameters, dt_s: float) -> float:
        if abs(current_a) < 1e-9:
            target = 0.0
        else:
            target = math.copysign(parameters.hysteresis_max_v, current_a)
        alpha = math.exp(-dt_s / parameters.hysteresis_tau_s)
        return alpha * previous_v + (1.0 - alpha) * target

    @staticmethod
    def _heat_generation_w(current_a: float, ocv_v: float, terminal_voltage_v: float, temperature_c: float, soc: float) -> float:
        irreversible_w = current_a * (ocv_v - terminal_voltage_v)
        entropic_w = -current_a * (temperature_c + 273.15) * interpolate(ENTROPIC_COEFF_V_PER_K, soc)
        return max(0.0, irreversible_w + entropic_w)


@dataclass(frozen=True)
class PackConfig:
    name: str
    series_cells: int
    parallel_cells: int = 1
    afe_average_depth: int = 16
    voltage_noise_std_v: float = 0.002
    temperature_noise_std_c: float = 0.10


@dataclass(frozen=True)
class PackOutput:
    pack_voltage_v: float
    current_a: float
    soc_min: float
    soc_avg: float
    soc_max: float
    temperature_min_c: float
    temperature_avg_c: float
    temperature_max_c: float
    heat_w: float
    cell_terminal_voltages_v: Tuple[float, ...]
    measured_cell_voltages_v: Tuple[float, ...]
    cell_temperatures_c: Tuple[float, ...]


class PackModel:
    """Series pack model built from individual cell models."""

    def __init__(self, config: PackConfig, cells: Sequence[CellModel], seed: int = 42) -> None:
        if len(cells) != config.series_cells:
            raise ValueError("number of cells must match config.series_cells")
        if config.parallel_cells != 1:
            raise ValueError("parallel_cells other than 1 are not implemented")
        self.config = config
        self.cells = list(cells)
        self._random = random.Random(seed)
        self._voltage_history: List[List[float]] = []
        for cell in self.cells:
            initial_v = cell.parameters.ocv_v(cell.state.soc)
            self._voltage_history.append([initial_v] * config.afe_average_depth)
        self._sample_index = 0

    @classmethod
    def create(
        cls,
        config: PackConfig,
        cell_parameters: Optional[CellParameters] = None,
        initial_soc: float = 0.50,
        initial_temperature_c: float = 25.0,
        seed: int = 42,
        cell_capacity_sigma: float = 0.003,
        cell_resistance_sigma: float = 0.05,
        ocv_offset_sigma_v: float = 0.003,
        thermal_capacity_sigma: float = 0.02,
    ) -> "PackModel":
        rng = random.Random(seed)
        base = cell_parameters or CellParameters()
        cells: List[CellModel] = []
        for _ in range(config.series_cells):
            cell_params = replace(
                base,
                ocv_offset_v=rng.gauss(0.0, ocv_offset_sigma_v),
                manufacturing_capacity_scale=max(0.90, rng.gauss(1.0, cell_capacity_sigma)),
                manufacturing_resistance_scale=max(0.70, rng.gauss(1.0, cell_resistance_sigma)),
                thermal_capacity_scale=max(0.80, rng.gauss(1.0, thermal_capacity_sigma)),
            )
            cell_state = CellState(soc=_clamp(initial_soc, 0.0, 1.0), temperature_c=initial_temperature_c)
            cells.append(CellModel(cell_params, cell_state))
        return cls(config, cells, seed=seed)

    def step(
        self,
        string_current_a: float,
        dt_s: float,
        ambient_c: float = 25.0,
        balancing_currents_a: Optional[Sequence[float]] = None,
    ) -> PackOutput:
        if balancing_currents_a is None:
            balancing_currents_a = [0.0] * self.config.series_cells
        if len(balancing_currents_a) != self.config.series_cells:
            raise ValueError("balancing_currents_a must match number of series cells")

        cell_outputs: List[CellOutput] = []
        measured_voltages: List[float] = []
        history_index = self._sample_index % self.config.afe_average_depth

        for index, cell in enumerate(self.cells):
            cell_current = string_current_a + balancing_currents_a[index]
            output = cell.step(cell_current, dt_s, ambient_c)
            cell_outputs.append(output)

            noisy_voltage = output.terminal_voltage_v + self._random.gauss(0.0, self.config.voltage_noise_std_v)
            self._voltage_history[index][history_index] = noisy_voltage
            measured_voltages.append(sum(self._voltage_history[index]) / self.config.afe_average_depth)

        self._sample_index += 1

        terminal_voltages = tuple(output.terminal_voltage_v for output in cell_outputs)
        temperatures = tuple(
            output.temperature_c + self._random.gauss(0.0, self.config.temperature_noise_std_c)
            for output in cell_outputs
        )
        soc_values = tuple(output.soc for output in cell_outputs)

        return PackOutput(
            pack_voltage_v=sum(terminal_voltages),
            current_a=string_current_a,
            soc_min=min(soc_values),
            soc_avg=sum(soc_values) / len(soc_values),
            soc_max=max(soc_values),
            temperature_min_c=min(temperatures),
            temperature_avg_c=sum(temperatures) / len(temperatures),
            temperature_max_c=max(temperatures),
            heat_w=sum(output.heat_w for output in cell_outputs),
            cell_terminal_voltages_v=terminal_voltages,
            measured_cell_voltages_v=tuple(measured_voltages),
            cell_temperatures_c=temperatures,
        )

    def run_constant_current(
        self,
        current_a: float,
        duration_s: float,
        dt_s: float = 1.0,
        ambient_c: float = 25.0,
    ) -> Iterable[Tuple[float, PackOutput]]:
        elapsed = 0.0
        while elapsed < duration_s:
            step_s = min(dt_s, duration_s - elapsed)
            output = self.step(current_a, step_s, ambient_c)
            elapsed += step_s
            yield elapsed, output


def make_pack_model(
    series_cells: int = 96,
    capacity_ah: float = 100.0,
    profile: str = "high-voltage",
    initial_soc: float = 0.50,
    initial_temperature_c: float = 25.0,
    seed: int = 42,
) -> PackModel:
    """Create a configurable generic series-string pack model."""
    return PackModel.create(
        PackConfig(name=f"generic_battery_{series_cells}s1p", series_cells=series_cells),
        cell_parameters=make_cell_parameters(profile=profile, capacity_ah=capacity_ah),
        initial_soc=initial_soc,
        initial_temperature_c=initial_temperature_c,
        seed=seed,
    )


def _make_model_from_args(args: argparse.Namespace) -> PackModel:
    return make_pack_model(
        series_cells=args.series_cells,
        capacity_ah=args.capacity_ah,
        profile=args.profile,
        initial_soc=args.initial_soc / 100.0,
        initial_temperature_c=args.initial_temperature_c,
        seed=args.seed,
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the generic battery pack model.")
    parser.add_argument("--series-cells", type=int, default=96)
    parser.add_argument("--capacity-ah", type=float, default=100.0)
    parser.add_argument("--profile", choices=("high-voltage", "low-voltage"), default="high-voltage")
    parser.add_argument("--current-a", type=float, default=0.0, help="Positive discharges, negative charges.")
    parser.add_argument("--duration-s", type=float, default=60.0)
    parser.add_argument("--dt-s", type=float, default=1.0)
    parser.add_argument("--ambient-c", type=float, default=25.0)
    parser.add_argument("--initial-soc", type=float, default=50.0, help="Initial SOC in percent.")
    parser.add_argument("--initial-temperature-c", type=float, default=25.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--csv", action="store_true", help="Print one row per step.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    model = _make_model_from_args(args)

    if args.csv:
        print("time_s,pack_voltage_v,current_a,soc_min_pct,soc_avg_pct,soc_max_pct,temp_min_c,temp_avg_c,temp_max_c,heat_w")

    last_output: Optional[PackOutput] = None
    for elapsed_s, output in model.run_constant_current(args.current_a, args.duration_s, args.dt_s, args.ambient_c):
        last_output = output
        if args.csv:
            print(
                f"{elapsed_s:.3f},{output.pack_voltage_v:.3f},{output.current_a:.3f},"
                f"{100.0 * output.soc_min:.4f},{100.0 * output.soc_avg:.4f},{100.0 * output.soc_max:.4f},"
                f"{output.temperature_min_c:.3f},{output.temperature_avg_c:.3f},{output.temperature_max_c:.3f},"
                f"{output.heat_w:.3f}"
            )

    if not args.csv and last_output is not None:
        print(f"model={model.config.name}")
        print(f"pack_voltage_v={last_output.pack_voltage_v:.3f}")
        print(f"current_a={last_output.current_a:.3f}")
        print(f"soc_avg_pct={100.0 * last_output.soc_avg:.4f}")
        print(f"temperature_avg_c={last_output.temperature_avg_c:.3f}")
        print(f"heat_w={last_output.heat_w:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
