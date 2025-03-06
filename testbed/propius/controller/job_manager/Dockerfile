FROM python:3.9

WORKDIR /
RUN mkdir propius

COPY ./propius/controller/requirements.txt propius/controller/requirements.txt
COPY ./pyproject-sys.toml /pyproject.toml

RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -e .
RUN pip3 install -r propius/controller/requirements.txt

RUN PROPIUS_HOME=$(pwd)
RUN echo export PROPIUS_HOME=$(pwd) >> ~/.bashrc
RUN . ~/.bashrc

CMD ["python", "-m", "propius.controller.job_manager"]