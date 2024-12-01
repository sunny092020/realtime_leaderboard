FROM python:3.9.18-bullseye

ARG POETRY_VER=1.6.1

RUN apt update -y \
    && apt-get install -y --no-install-recommends \
    openjdk-11-jdk=11.0.* \
    && pip install poetry==$POETRY_VER

WORKDIR /taskscripts

COPY pyproject.toml ./
COPY app.py const.py tests/ ./

RUN poetry lock \
    && poetry export -f requirements.txt > requirements.txt \
    && pip install -r requirements.txt \
    && rm requirements.txt

EXPOSE 5000

CMD ["python", "app.py"]
