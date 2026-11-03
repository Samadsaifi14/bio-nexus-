# Self-contained Nextflow + samtools/bcftools runtime for the BioNexus NGS workflow.
# The Nextflow launcher is copied from the official image; tools come from Ubuntu.
FROM nextflow/nextflow:24.10.5 AS nextflow

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV NXF_HOME=/opt/nextflow
ENV NXF_ANSI_LOG=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        coreutils \
        curl \
        gawk \
        grep \
        python3 \
        unzip \
        openjdk-17-jre-headless \
        samtools \
        bcftools \
    && rm -rf /var/lib/apt/lists/*

COPY --from=nextflow /usr/local/bin/nextflow /usr/local/bin/nextflow

RUN mkdir -p "${NXF_HOME}" \
    && chmod 0755 /usr/local/bin/nextflow \
    && nextflow -version

WORKDIR /work
CMD ["bash"]
