# BMI container for EPA SWMM5 via pyswmm, served with grpc4bmi.
#
# Build:
#   docker build --tag swmm-grpc4bmi:v0.0.1 .
#
# Test from Python:
#   from grpc4bmi.bmi_client_docker import BmiClientDocker
#   model = BmiClientDocker('swmm-grpc4bmi:v0.0.1', work_dir='/tmp', delay=1)
#   model.get_component_name()
#   del model
#
# Debug interactively:
#   docker run --tty --interactive swmm-grpc4bmi:v0.0.1 bash

FROM mambaorg/micromamba:1.3.1

LABEL org.opencontainers.image.source="https://github.com/eWaterCycle/swmm-bmi"

# pyswmm bundles the SWMM5 C library via swmm-toolkit; no separate SWMM install needed.
RUN micromamba install -y -n base -c conda-forge python=3.10 && \
    micromamba clean --all --yes

ARG MAMBA_DOCKERFILE_ACTIVATE=1

COPY . /opt/swmm-bmi
RUN pip install /opt/swmm-bmi/

RUN pip install grpc4bmi==0.4.0

CMD run-bmi-server --name "swmm_bmi.SwmmBmi" --port 55555 --debug
