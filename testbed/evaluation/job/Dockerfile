FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y python3.9 python3-pip python3.9-venv && \
    apt-get clean

WORKDIR /

RUN mkdir evaluation
RUN mkdir propius

COPY ./evaluation/requirements_peripheral.txt evaluation/requirements_peripheral.txt

RUN python3.9 -m venv venv
ENV PATH="/venv/bin:$PATH"

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r evaluation/requirements_peripheral.txt

RUN pip install "numpy<2"

ENTRYPOINT ["/evaluation/job/entrypoint.sh"]