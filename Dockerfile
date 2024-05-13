FROM python:3.9-alpine

#install dependencies for build pip packages
RUN apk add protobuf gcc libc-dev linux-headers python3 py3-pip aws-cli

#install jinja2
RUN pip3 install --no-cache-dir Jinja2==3.1.2

#copy and install dependencies for telliot core
WORKDIR /usr/src/app/telliot-core
COPY ./telliot-core .
RUN pip install -e .
COPY ./change_address.py .

#copy and install dependencies for telliot feeds
WORKDIR /usr/src/app/telliot-feeds
COPY . .
RUN pip install -e .

COPY ./expect.py .
