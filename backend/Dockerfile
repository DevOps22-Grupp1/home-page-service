FROM python:3.12-slim
WORKDIR /app
# Flask 2.3 to match the Werkzeug pin
RUN pip install --no-cache-dir flask==2.3.3 prometheus-flask-exporter requests flask_login Werkzeug==2.3.7
COPY ./app.py /app/app.py
COPY ./templates /app/templates
# The CSS, images and favicons
COPY ./static /app/static
# Not as root
RUN useradd --system --no-create-home app
USER app
EXPOSE 4004
CMD ["python","-u", "app.py"]


# docker build -t service1 .
