FROM python:3.7.2

COPY hds /app/hds
COPY ./requirements.txt /app/requirements.txt

WORKDIR /app/

RUN pip install -r /app/requirements.txt
ENV CERTPATH "/app/data/cert.pem"
ENV KEYPATH "/app/data/key.pem"

CMD ["python3", "-m", "hds.directoryservice"]