FROM python
RUN pip install flask requests stripe prometheus-flask-exporter flask-login
COPY ./app.py /app.py
COPY ./templates /templates
CMD ["python", "app.py"]


# docker build -t service1 .      