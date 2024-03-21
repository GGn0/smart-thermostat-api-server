# syntax=docker/dockerfile:1

FROM python:3.8-slim-buster

WORKDIR /smart-thermostat

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY flaskapp.py flaskapp.py

CMD [ "python3", "-m" , "flaskapp", "run", "--host=0.0.0.0"]
