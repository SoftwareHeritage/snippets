FROM python:3.7

RUN pip install flask

RUN mkdir /app /data
VOLUME /data

ENTRYPOINT ["flask"]
CMD ["run", "--host", "0.0.0.0"]

WORKDIR /app
ARG VERSION=v0
ENV FLASK_APP=demo-${VERSION}.py
ENV VERSION=${VERSION}
COPY demo-${VERSION}.py /app
