from typing import Any, Tuple
import datetime
import numpy as np
from bmipy import Bmi
from pyswmm import Simulation, Subcatchments, Nodes, Links, RainGages

from swmm_bmi import utils


_EPOCH = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)

# Grid IDs
_SUBCATCHMENT_GRID = 0
_NODE_GRID = 1
_LINK_GRID = 2
_RAINGAGE_GRID = 3

# Precipitation units depend on the model's FLOW_UNITS system (US -> in/hr,
# SI -> mm/hr); the actual string is resolved per-instance in initialize().
_PRECIP_UNITS = {"US": "in hr-1", "SI": "mm hr-1"}

# var_name -> (grid_id, units)
_OUTPUT_VARS: dict[str, tuple[int, str]] = {
    "subcatchment_runoff": (_SUBCATCHMENT_GRID, "m3 s-1"),
    "node_depth":          (_NODE_GRID,         "m"),
    "node_flooding":       (_NODE_GRID,         "m3 s-1"),
    "link_flow":           (_LINK_GRID,         "m3 s-1"),
}
_INPUT_VARS: dict[str, tuple[int, str]] = {
    "node_lateral_inflow": (_NODE_GRID,     "m3 s-1"),
    # Rain-gage precipitation rate; units set per-instance (see _precip_units).
    "precipitation":       (_RAINGAGE_GRID, "mm hr-1"),
}
_ALL_VARS = {**_OUTPUT_VARS, **_INPUT_VARS}


class SwmmBmi(Bmi):
    """BMI wrapper for EPA SWMM5 via pyswmm."""

    def initialize(self, config_file: str) -> None:
        self.config: dict[str, Any] = utils.read_config(config_file)
        inp_file_path = utils.get_inp_file(self.config, config_file)
        # report_file_path = utils.get_inp_file(self.config, config_file, 'rpt_file')
        # out_file_path = utils.get_inp_file(self.config, config_file, 'out_file')

        self._sim = Simulation(
            inputfile=str(inp_file_path),
            # reportfile=str(report_file_path),
            # outputfile=str(out_file_path),
        )
        self._sim.__enter__()

        # Advance by the model's own routing interval each BMI step.
        self._timestep_s = utils.parse_routing_step(inp_file_path)
        self._sim.step_advance(int(self._timestep_s))

        # Cache ordered lists so indices stay stable across calls.
        self._subcatchments = list(Subcatchments(self._sim))
        self._nodes = list(Nodes(self._sim))
        self._links = list(Links(self._sim))
        self._raingages = list(RainGages(self._sim))

        # SWMM reports/accepts rain-gage rates in the model's own unit system
        # (US -> in/hr, SI -> mm/hr). Resolve the label for get_var_units().
        self._precip_units = _PRECIP_UNITS[utils.parse_flow_units(inp_file_path)]


        # Seed current time from start_time — current_time is unavailable in
        # swmm-toolkit before the first solver step has been taken.
        self._current_time_s: float = _to_unix(self._sim.start_time)

    def update(self) -> None:
        try:
            next(self._sim)
        except StopIteration:
            # pyswmm raises StopIteration when the simulation is complete.
            # Sync to end_time so callers see get_current_time() == get_end_time().
            self._current_time_s = _to_unix(self._sim.end_time)
            return
        # Prefer pyswmm's own current_time; fall back to incrementing by timestep
        # (some swmm-toolkit versions raise if called between steps).
        try:
            self._current_time_s = _to_unix(self._sim.current_time)
        except Exception:
            self._current_time_s += self._timestep_s

    def update_until(self, time: float) -> None:
        while self.get_current_time() < time:
            self.update()

    def finalize(self) -> None:
        self._sim.__exit__(None, None, None)

    # --- component ---

    def get_component_name(self) -> str:
        return "SWMM"

    # --- variable metadata ---

    def get_output_var_names(self) -> Tuple[str, ...]:
        return tuple(_OUTPUT_VARS.keys())

    def get_input_var_names(self) -> Tuple[str, ...]:
        return tuple(_INPUT_VARS.keys())

    def get_output_item_count(self) -> int:
        return len(_OUTPUT_VARS)

    def get_input_item_count(self) -> int:
        return len(_INPUT_VARS)

    def get_var_units(self, var_name: str) -> str:
        if var_name == "precipitation":
            return self._precip_units
        return _ALL_VARS[var_name][1]

    def get_var_grid(self, var_name: str) -> int:
        return _ALL_VARS[var_name][0]

    def get_var_type(self, var_name: str) -> str:
        return "float64"

    def get_var_itemsize(self, var_name: str) -> int:
        return np.dtype("float64").itemsize

    def get_var_nbytes(self, var_name: str) -> int:
        return self.get_grid_size(self.get_var_grid(var_name)) * self.get_var_itemsize(var_name)

    def get_var_location(self, var_name: str) -> str:
        return "node"

    # --- get / set values ---

    def get_value(self, var_name: str, dest: np.ndarray) -> np.ndarray:
        match var_name:
            case "subcatchment_runoff":
                dest[:] = [sc.runoff for sc in self._subcatchments]
            case "node_depth":
                dest[:] = [n.depth for n in self._nodes]
            case "node_flooding":
                dest[:] = [n.flooding for n in self._nodes]
            case "link_flow":
                dest[:] = [lnk.flow for lnk in self._links]
            case "precipitation":
                dest[:] = [g.total_precip for g in self._raingages]
            case _:
                raise ValueError(f"Unknown variable: {var_name}")
        return dest

    def set_value(self, var_name: str, src: np.ndarray) -> None:
        match var_name:
            case "node_lateral_inflow":
                # Inject a lateral inflow [m3/s] at each node.
                # The value is held constant until the next set_value call.
                for node, val in zip(self._nodes, src):
                    node.generated_inflow(float(val))
            case "precipitation":
                # Set each rain gage's precipitation rate (model units: in/hr
                # or mm/hr). Held constant until the next set_value call, so a
                # daily forcing value persists across all sub-step updates.
                for gage, val in zip(self._raingages, src):
                    gage.total_precip = float(val)
            case _:
                raise ValueError(f"Cannot set variable: {var_name}")

    def get_value_at_indices(
        self, name: str, dest: np.ndarray, inds: np.ndarray
    ) -> np.ndarray:
        buf = np.empty(self.get_grid_size(self.get_var_grid(name)))
        self.get_value(name, buf)
        dest[:] = buf[inds]
        return dest

    def set_value_at_indices(
        self, name: str, inds: np.ndarray, src: np.ndarray
    ) -> None:
        buf = np.empty(self.get_grid_size(self.get_var_grid(name)))
        self.get_value(name, buf)
        buf[inds] = src
        self.set_value(name, buf)

    def get_value_ptr(self, var_name: str) -> np.ndarray:
        raise NotImplementedError("get_value_ptr is not supported for SWMM")

    # --- time ---

    def get_start_time(self) -> float:
        return _to_unix(self._sim.start_time)

    def get_end_time(self) -> float:
        return _to_unix(self._sim.end_time)

    def get_current_time(self) -> float:
        return self._current_time_s

    def get_time_step(self) -> float:
        return self._timestep_s

    def get_time_units(self) -> str:
        return "seconds since 1970-01-01 00:00:00.0 +0000"

    # --- grid ---

    def get_grid_type(self, grid: int) -> str:
        return "points"

    def get_grid_rank(self, grid: int) -> int:
        return 2

    def get_grid_size(self, grid: int) -> int:
        match grid:
            case 0:
                return len(self._subcatchments)
            case 1:
                return len(self._nodes)
            case 2:
                return len(self._links)
            case 3:
                return len(self._raingages)
            case _:
                raise ValueError(f"Unknown grid id: {grid}")

    def get_grid_shape(self, grid: int, shape: np.ndarray) -> np.ndarray:
        shape[:] = [self.get_grid_size(grid)]
        return shape

    def get_grid_x(self, grid: int, x: np.ndarray) -> np.ndarray:
        match grid:
            case 0:  # subcatchments: no standard centroid in pyswmm API
                x[:] = 0.0
            case 1:  # nodes: actual model coordinates
                x[:] = [_coord(n, 0) for n in self._nodes]
            case 2:  # links: no point geometry
                x[:] = 0.0
            case 3:  # rain gages: no point geometry in pyswmm API
                x[:] = 0.0
        return x

    def get_grid_y(self, grid: int, y: np.ndarray) -> np.ndarray:
        match grid:
            case 0:
                y[:] = 0.0
            case 1:
                y[:] = [_coord(n, 1) for n in self._nodes]
            case 2:
                y[:] = 0.0
            case 3:
                y[:] = 0.0
        return y

    def get_grid_spacing(self, grid: int, spacing: np.ndarray) -> np.ndarray:
        raise NotImplementedError("not applicable for points grid")

    def get_grid_origin(self, grid: int, origin: np.ndarray) -> np.ndarray:
        raise NotImplementedError("not applicable for points grid")

    def get_grid_node_count(self, grid: int) -> int:
        return self.get_grid_size(grid)

    def get_grid_edge_count(self, grid: int) -> int:
        raise NotImplementedError()

    def get_grid_edge_nodes(self, grid: int, edge_nodes: np.ndarray) -> np.ndarray:
        raise NotImplementedError()

    def get_grid_face_count(self, grid: int) -> int:
        raise NotImplementedError()

    def get_grid_face_edges(self, grid: int, face_edges: np.ndarray) -> np.ndarray:
        raise NotImplementedError()

    def get_grid_face_nodes(self, grid: int, face_nodes: np.ndarray) -> np.ndarray:
        raise NotImplementedError()

    def get_grid_nodes_per_face(
        self, grid: int, nodes_per_face: np.ndarray
    ) -> np.ndarray:
        raise NotImplementedError()

    def get_grid_z(self, grid: int, z: np.ndarray) -> np.ndarray:
        raise NotImplementedError()


def _to_unix(dt: datetime.datetime) -> float:
    """Convert datetime to seconds since 1970-01-01 UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return (dt - _EPOCH).total_seconds()


def _coord(node, idx: int) -> float:
    """Return node coordinate at index 0 (x) or 1 (y), or 0.0 if unavailable."""
    try:
        coords = node.coordinates
        if coords:
            return float(coords[idx])
    except (AttributeError, TypeError, IndexError):
        pass
    return 0.0
