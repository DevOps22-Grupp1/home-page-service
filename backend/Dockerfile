FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir flask prometheus-flask-exporter requests flask_login
COPY ./app.py /app/app.py
COPY ./templates /app/templates
# Not as root
RUN useradd --system --no-create-home app
USER app
EXPOSE 4004
CMD ["python", "app.py"]


# docker build -t service1 .
