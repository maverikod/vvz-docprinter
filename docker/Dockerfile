# DocPrinter HTTP service image
# Build from repository root: ./docker/build.sh
#
# Author: Vasiliy Zdanovskiy
# email: vasilyvz@gmail.com

FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY docprinter /app/docprinter
COPY config /app/config

RUN mkdir -p /app/logs

EXPOSE 9001

# Default 9001; host maps the same port via ``docker/run.sh`` (``-p 9001:9001``).
CMD ["python", "-m", "docprinter", "run", "-c", "config/docker.json", "--host", "0.0.0.0", "--port", "9001"]
