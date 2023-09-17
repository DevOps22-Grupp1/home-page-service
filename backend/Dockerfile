FROM python
RUN pip install flask prometheus-flask-exporter requests flask_login
COPY ./app.py /app.py
COPY ./templates /templates
CMD ["python", "app.py"]


# docker build -t service1 .      