FROM python:3.9.5-slim-buster
WORKDIR /usr/src/
ENV PYTHONPATH "${PYTHONPATH}:/usr/src/cr_stats"
COPY . .
RUN apt-get update -y \
    && apt-get -y install git build-essential python3-dev libyaml-dev gcc \
    && pip install -r requirements.txt
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "app:app", "--reload", "--reload-engine", "poll"]