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

    # look in products.html how to use the forloop(array) correct and not making it go double. At this moment it goes double for visual purpose #
    # status is just a demo list how it could look like on the page #
@app.route("/server/")
def server():

    res1 = requests.get("http://scamazon-product-catalog-service-1:4005")
    if res1.status_code == 200:
        r1 = "Success"
    else:
        r1 = jsonify({'error': 'Failed to fetch data'})
    
    res2 = requests.get("http://scamazon-user-management-service-1:4006")
    if res2.status_code == 200:
        r2 = "Success"
    else:
        r2 = jsonify({'error': 'Failed to fetch data'})
    
    res3 = requests.get("http://scamazon-order-processing-service-1:4007")
    if res3.status_code == 200:
        r3 = "Success"
    else:
        r3 = jsonify({'error': 'Failed to fetch data'})

    
    status = [{"name": "product-catalog-service", "status": r1.text}, {"name": "user-managament-service", "status": r2.text}, {"name": "order-processing-service", "status": r3.text}]


    return render_template("server.html", utc_dt=datetime.datetime.utcnow(), status=status)
### Make requests to the other services and return the result ok or not ok ###

#def check_server_status():
    # r1 = requests.get("http://order-processing-service:5001")
    # r2 = requests.get("http://scamazon-product-catalog-service-1:4005/")
    # return f"order-processing-service says: {r1.text}! - user-managament-service says {r2.text} - product-catalog-service says {r3.text}" 


# Very important to disable debug mode
app.run(host="0.0.0.0", port=4004, debug=True)
