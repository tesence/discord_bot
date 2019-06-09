FROM python:3.6

WORKDIR /gumo
ADD requirements.txt /gumo

RUN pip install -r requirements.txt
