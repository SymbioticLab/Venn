FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y python3.9 python3-pip python3.9-venv && \
    apt-get install iperf &&\
    apt-get clean

WORKDIR /
RUN mkdir propius

COPY ./requirements.txt ./requirements.txt
COPY ./pyproject.toml ./pyproject.toml

RUN python3.9 -m venv env
ENV PATH="/env/bin:$PATH"
# ENV PROPIUS_HOME="/propius"

RUN python -m pip install --upgrade pip
RUN pip3 install -r ./requirements.txt

RUN pip install -e .
RUN pip install torch==2.1.2

CMD ["propius-parameter-server-leaf"]