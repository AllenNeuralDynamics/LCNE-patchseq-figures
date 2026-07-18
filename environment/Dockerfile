# hash:sha256:f021ab0082d32d2954b63da31e988d47a581ca94879eb15b3627e51ed45c93a3
ARG REGISTRY_HOST
FROM $REGISTRY_HOST/codeocean/mambaforge3:24.5.0-0-python3.12.4-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive

RUN pip install --no-cache-dir \
    matplotlib==3.10.9 \
    numpy==2.2.6 \
    pandas==2.3.3