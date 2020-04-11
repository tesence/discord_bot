FROM python:3.7

WORKDIR /gumo
ADD requirements.txt /gumo

RUN pip install -r requirements.txt
