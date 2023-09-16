from flask import Flask, render_template
import datetime
import requests
from prometheus_flask_exporter import PrometheusMetrics

app = Flask(__name__)
metrics = PrometheusMetrics(app)

metrics.info("app_info", "home-page-service", version="1.0.0")


@metrics.counter(
    "invocation_by_method",
    "Number of invocations by HTTP method",
)
@app.route("/")
def hello():
    return render_template("index.html", utc_dt=datetime.datetime.utcnow())

@app.route("/about/")
def about():
    return render_template("about.html")

@app.route("/products/")
def products():

    # AT THIS MOMENT NOT WORKING - RESEARCH HOW TO GET THE DATA FROM THE OTHER SERVICE #
    products = requests.get('http://scamazon-product-catalog-service-1:4005/api/products').json()
    products = products.sringify()
    

    return render_template("products.html", products=products, utc_dt=datetime.datetime.utcnow())

@app.route("/server/")
def server():

    r1 = requests.get("http://scamazon-product-catalog-service-1:4005")
    r2 = requests.get("http://scamazon-user-management-service-1:4006")
    r3 = requests.get("http://scamazon-order-processing-service-1:4007")

    status = [r1.text, r2.text, r3.text]
    services = ["product-catalog-service", "user-managament-service" ,"order-processing-service" ]
    return render_template("server.html", utc_dt=datetime.datetime.utcnow(), status=status, services=services)
    # return f"{r1.text}! - {r2.text}! - {r3.text}!"
    
    
    # look in products.html how to use the forloop(array) correct and not making it go double. At this moment it goes double for visual purpose #
    # status is just a demo list how it could look like on the page #
    # 
    # 
    # return render_template("server.html", utc_dt=datetime.datetime.utcnow(), status=status, services=services)

### Make requests to the other services and return the result ok or not ok ###

#def check_server_status():
      


# Very important to disable debug mode
app.run(host="0.0.0.0", port=4004, debug=False)
