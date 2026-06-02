# Base container for a BMI model written in Python
#
# Activates a default conda base environment with micromamba. While it may not
# always be necessary, many hydrological models may at some point want to
# install conda dependencies, which can be a struggle. This image should provide
# a good starting point.
#
# For details on the base image, see
# https://github.com/mamba-org/micromamba-docker
#
#
# To build the image, run
#
#   docker build --tag leakybucket-grpc4bmi:v0.0.1 .
#
# If you use podman, you may need to add `--format docker`
#
#   docker build --format docker --tag leakybucket-grpc4bmi:v0.0.1 .
#
# To talk to the model from outside the container, use grpc4bmi client
#
#   from grpc4bmi.bmi_client_docker import BmiClientDocker
#   model = BmiClientDocker('leakybucket-grpc4bmi:v0.0.1', work_dir='/tmp', delay=1)
#
# To debug the container, you can override the grpc4bmi command
#
#   docker run --tty --interactive leakybucket-grpc4bmi:v0.0.1 bash
#
# This will spawn a new bash terminal running inside the docker container

FROM mambaorg/micromamba:1.3.1

# Here you can point to the source repository of this Dockerfile:
LABEL org.opencontainers.image.source="https://github.com/eWaterCycle/leakybucket-bmi"

# Install Python + additional conda-dependencies,
# Here I added cartopy as an example
RUN micromamba install -y -n base -c conda-forge python=3.10 cartopy && \
    micromamba clean --all --yes

# Make sure the conda environment is activated for the remaining build
# instructions below
ARG MAMBA_DOCKERFILE_ACTIVATE=1  # (otherwise python will not be found)

# Install leakybucket.LeakyBucketBmi
COPY . /opt/leakybucket
RUN pip install /opt/leakybucket/

RUN pip install grpc4bmi==0.4.0

# Default command should be to run GRPC4BMI server
# Don't override micromamba's entrypoint as that activates conda!
CMD run-bmi-server --name "leakybucket.LeakyBucketBmi" --port 55555 --debug
