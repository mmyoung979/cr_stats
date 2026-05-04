FROM python:3.9-slim
WORKDIR /usr/src/
ENV PYTHONPATH "${PYTHONPATH}:/usr/src/cr_stats"
COPY . .
RUN apt-get update -y \
    && apt-get -y install git libpq-dev build-essential python3-dev libyaml-dev gcc \
    && python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt
EXPOSE 5001
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "4", "app:app", "--reload", "--reload-engine", "poll"]
