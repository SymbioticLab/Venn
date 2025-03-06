FROM python:3.9

WORKDIR /
RUN mkdir propius
RUN mkdir propius/client_manager

COPY ./propius/controller/requirements.txt propius/controller/requirements.txt
COPY ./propius/controller/client_manager/entrypoint.sh propius/controller/client_manager/entrypoint.sh
COPY ./pyproject-sys.toml /pyproject.toml

RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -e .
RUN pip3 install -r propius/controller/requirements.txt
RUN chmod +x propius/controller/client_manager/entrypoint.sh

RUN PROPIUS_HOME=$(pwd)
RUN echo export PROPIUS_HOME=$(pwd) >> ~/.bashrc
RUN . ~/.bashrc

ENTRYPOINT ["./propius/controller/client_manager/entrypoint.sh"]