# hash:sha256:cb72ef16bdb9997584a049e599e913d2b3dfa7064d6b88debb4af6ebe7a73718
ARG REGISTRY_HOST
FROM $REGISTRY_HOST/codeocean/mambaforge3:24.5.0-0-python3.12.4-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive
ARG GIT_ASKPASS
COPY git-ask-pass /

RUN pip install -U --no-cache-dir \
    dandi==0.81.0 \
    h5py==3.16.0 \
    matplotlib==3.10.9 \
    numpy==2.2.6 \
    pandas==2.3.3 \
    remfile==0.1.15 \
    scipy==1.15.3

COPY postInstall /
RUN --mount=type=secret,id=secrets . /run/secrets/secrets \
    && /postInstall
