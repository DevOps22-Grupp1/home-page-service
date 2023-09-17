from flask import Flask, render_template, jsonify
import datetime
import json
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
    response = requests.get('http://scamazon-product-catalog-service-1:4005/api/products') 

    if response.status_code == 200:
        products = json.loads(response.text)
    else:
        return jsonify({'error': 'Failed to fetch data'})
  
    return render_template("products.html", products=products)
#  images=images, prices=prices

@app.route("/server/")
def server():
    # look in products.html how to use the forloop(array) correct and not making it go double. At this moment it goes double for visual purpose #
    # status is just a demo list how it could look like on the page #
    r1 = requests.get("http://order-processing-service:4007")
    r2 = requests.get("http://user-managament-service:4006/")
    r3 = requests.get("http://scamazon-product-catalog-service-1:4005/")
    
    
    status = [r1.text, r2.text, r3.text]
    services = ["order-processing-service", "user-managament-service", "product-catalog-service"]
    return render_template("server.html", utc_dt=datetime.datetime.utcnow(), status=status, services=services)

### Make requests to the other services and return the result ok or not ok ###

#def check_server_status():
    # r1 = requests.get("http://order-processing-service:5001")
    # r2 = requests.get("http://scamazon-product-catalog-service-1:4005/")
    # return f"order-processing-service says: {r1.text}! - user-managament-service says {r2.text} - product-catalog-service says {r3.text}" 


# Very important to disable debug mode
app.run(host="0.0.0.0", port=4004, debug=False)
