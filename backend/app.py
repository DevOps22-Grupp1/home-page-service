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

    try:
        response = requests.get('http://scamazon-product-catalog-service-1:4005/api/products') 
        if response.status_code == 200:
            products = json.loads(response.text)
    except requests.exceptions.RequestException as e:
        products = 'Failed to fetch data'
  
    return render_template("products.html", products=products)


    ### Make requests to the other services and return the result ok or not ok ###
@app.route("/server/")
def server():
    try:
        res1 = requests.get("http://scamazon-product-catalog-service-1:4005")
        if res1.status_code == 200:
            r1 = res1.text
    except requests.exceptions.RequestException as e:
        r1 = 'Failed to fetch data'
    
    
    try:
        res2 = requests.get("http://scamazon-user-management-service-1:4006")
        if res2.status_code == 200:
            r2 = res2.text
    except requests.exceptions.RequestException as e:
        r2 = 'Failed to fetch data'
    
    
    try:
        res3 = requests.get("http://scamazon-order-processing-service-1:4007")
        if res3.status_code == 200:
            r3 = res3.text
    except requests.exceptions.RequestException as e:
        r3 = 'Failed to fetch data'
    

    
    status = [{"name": "product-catalog-service", "status": r1}, {"name": "user-managament-service", "status": r2}, {"name": "order-processing-service", "status": r3}]


    return render_template("server.html", utc_dt=datetime.datetime.utcnow(), status=status)

 


# Very important to disable debug mode
app.run(host="0.0.0.0", port=4004, debug=True)
