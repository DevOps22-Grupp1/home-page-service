FROM python
RUN pip install flask prometheus-flask-exporter requests
COPY ./app.py /app.py
CMD ["python", "app.py"]


# docker build -t service1 .      