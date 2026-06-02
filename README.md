# Python BMI example: a leaky bucket model 🪣

This repository is a template for creating a new hydrological model in Python, using the [Basic Model Interface (BMI)](https://bmi.readthedocs.io/).

The goal is to plug this model into [eWaterCycle](https://ewatercycle.readthedocs.io/), and as such forcing data and configuration file handling will be performed using eWaterCycle.
This is implemented in the [ewatercycle-leakybucket repository](https://github.com/eWaterCycle/ewatercycle-leakybucket).


## Installation

Install this package alongside your prefered Python environment.

```console
pip install leakybucket
```

To be able to run the demo notebook, this has to be an environment with `ewatercycle` already installed.

## Implementing your own model

To implement your own model, clone or download this repository.

You can use the [`LumpedBmiTemplate`](src/leakybucket/lumped_bmi.py) as a starting point. You can use the [LeakyBucket BMI implementation](src/leakybucket/leakybucket_bmi.py) as an example.

## Sharing your model: packaging it in a container 📦

To make it easier for others to use your model, you should package it into a container.
In this repository is the [`Dockerfile`](Dockerfile), which contains all the steps to install the model.

Additionally, the container installs [grpc4bmi](https://github.com/eWaterCycle/grpc4bmi). Grpc4bmi allows communication with the model's BMI when it is packaged in the container, and is thus essential to add to the container.

### Building and testing the container

If you have docker installed, you can build the container by doing:

```
docker build -t leakybucket-grpc4bmi:v0.0.1 .
```

To start the container and test it, run the following command in your Python terminal:

```python
from grpc4bmi.bmi_client_docker import BmiClientDocker
model = BmiClientDocker('leakybucket-grpc4bmi:v0.0.1', work_dir='/tmp')
model.get_component_name()
del model
```

If somehing went wrong, you can look around in the container by running:

```sh
docker run -it leakybucket-grpc4bmi:v0.0.1 bash
```

### Publishing the container
To build this container and push it to the Github container registry you need to set up an acces token first. Information on this is available on the [Github Packages documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

When you are set up you can build and push the container as such:

```
docker build -t ghcr.io/ewatercycle/leakybucket-grpc4bmi:v0.1.0 .
docker push ghcr.io/ewatercycle/leakybucket-grpc4bmi:v0.1.0
```

It will then become available on [Github Packages](https://github.com/eWaterCycle/leakybucket-bmi/pkgs/container/leakybucket-grpc4bmi).
Note that you still have to mark the container as public before others can access it.

## License

`leakybucket-bmi` is distributed under the terms of the [Apache-2.0](https://spdx.org/licenses/Apache-2.0.html) license.
