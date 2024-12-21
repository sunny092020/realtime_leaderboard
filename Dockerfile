FROM python:3.9.18-bullseye

ARG POETRY_VER=1.6.1

RUN apt update -y \
    && apt-get install -y --no-install-recommends \
    openjdk-11-jdk=11.0.* \
    && pip install poetry==$POETRY_VER \
    && pip install debugpy

WORKDIR /app

COPY pyproject.toml ./

RUN poetry lock \
    && poetry export -f requirements.txt > requirements.txt \
    && pip install -r requirements.txt \
    && rm requirements.txt

EXPOSE 5000
EXPOSE 5678

WORKDIR /app/src

CMD ["python", "-m", "debugpy", "--listen", "0.0.0.0:5678", "--wait-for-client", "app.py"]