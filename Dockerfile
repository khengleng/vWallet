FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml poetry.lock /app/

RUN pip install --no-cache-dir pip setuptools wheel
RUN pip install --no-cache-dir django djangorestframework celery redis web3 eth-account

COPY . /app
RUN pip install -e /app

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
