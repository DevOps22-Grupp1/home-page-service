FROM python:3.9-slim
RUN pip install flask prometheus-flask-exporter requests flask_login Werkzeug==2.3.7
COPY ./app.py /app.py
COPY ./templates /templates
CMD ["python", "app.py"]


# docker build -t service1 .      