# swmm-bmi 🌧️

A [Basic Model Interface (BMI)](https://bmi.readthedocs.io/) wrapper for **EPA SWMM5**
(the Storm Water Management Model), built on top of [pyswmm](https://www.pyswmm.org/).

It exposes a running SWMM simulation through the standard BMI calls (`initialize`,
`update`, `get_value`, `set_value`, `finalize`, …) so that SWMM can be driven
step-by-step, coupled to other models, and run inside
[eWaterCycle](https://ewatercycle.readthedocs.io/).

## Installation

```console
pip install swmm-bmi
```

Or install from a clone of this repository:

```console
pip install .
```

Dependencies (`pyswmm`, `bmipy`, `numpy`, `pyyaml`) are installed automatically.
`pyswmm` bundles the SWMM5 C library via `swmm-toolkit`, so no separate SWMM
installation is required.

## Usage of just the Container!!

The wrapper is initialized with a small JSON config file that points to a SWMM
`.inp` input file. All model parameters and timing (start/end dates, routing step,
flow units) are read from the `.inp` file itself. 
If you need to use a data file.dat, give it the same filename as the input file, but replace the suffix.

**`example_config.json`:**

```json
{
  "inp_file": "example_model.inp"
}
```

A relative `inp_file` path is resolved relative to the config file's location.

**Driving the model from Python:**

```python
import numpy as np
from swmm_bmi import SwmmBmi

model = SwmmBmi()
model.initialize("example_config.json")

# Step through the whole simulation
n_nodes = model.get_grid_size(1)
while model.get_current_time() < model.get_end_time():
    model.update()
    depth = model.get_value("node_depth", np.empty(n_nodes))

model.finalize()
```

See [`demo_swmm_bmi.ipynb`](demo_swmm_bmi.ipynb) for a full worked example that
inspects the BMI metadata, runs the bundled `example_model.inp`, plots the
results, and injects external lateral inflow.

## Exposed variables

Each BMI variable is backed by one of four SWMM element types, addressed as
separate BMI grids. Values are reported/accepted in SI units regardless of the
model's own flow-unit system.

| Grid | Element type   |
|------|----------------|
| 0    | subcatchments  |
| 1    | nodes          |
| 2    | links          |
| 3    | rain gages     |

**Output variables** (`get_value`):

| Variable              | Grid          | Units    |
|-----------------------|---------------|----------|
| `subcatchment_runoff` | subcatchments | m3 s-1   |
| `node_depth`          | nodes         | m        |
| `node_flooding`       | nodes         | m3 s-1   |
| `link_flow`           | links         | m3 s-1   |

**Input variables** (`set_value`):

| Variable              | Grid       | Units                    | Notes |
|-----------------------|------------|--------------------------|-------|
| `node_lateral_inflow` | nodes      | m3 s-1                   | Injected via pyswmm's `Node.generated_inflow`; held constant until the next `set_value`. |
| `precipitation`       | rain gages | in hr-1 / mm hr-1        | Units follow the model's flow-unit system (US → in/hr, SI → mm/hr). |

A typical eWaterCycle coupling pre-computes forcing externally and injects it each
timestep with `set_value("node_lateral_inflow", values)` or
`set_value("precipitation", values)`, then calls `update()`.

## Containerizing with grpc4bmi 📦

The included [`Dockerfile`](Dockerfile) packages the model and serves its BMI over
[grpc4bmi](https://github.com/eWaterCycle/grpc4bmi), which lets other tools (such as
eWaterCycle) talk to the model running in an isolated container.

Build the container:

```console
docker build -t swmm-grpc4bmi:v0.0.1 .
```

Test it from Python:

```python
from grpc4bmi.bmi_client_docker import BmiClientDocker

model = BmiClientDocker("swmm-grpc4bmi:v0.0.1", work_dir="/tmp", delay=1)
print(model.get_component_name())
del model
```

Inspect the container interactively:

```console
docker run -it swmm-grpc4bmi:v0.0.1 bash
```

### Publishing the container

To push to the GitHub container registry (set up an access token first — see the
[GitHub Packages documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)):

```console
docker build -t ghcr.io/ewatercycle/swmm-grpc4bmi:v0.0.1 .
docker push ghcr.io/ewatercycle/swmm-grpc4bmi:v0.0.1
```

Remember to mark the package as public before others can pull it.

## License

`swmm-bmi` is distributed under the terms of the
[Apache-2.0](https://spdx.org/licenses/Apache-2.0.html) license.
