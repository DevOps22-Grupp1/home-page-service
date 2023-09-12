from flask import Flask, render_template
import datetime
#import requests
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

    # These arrays / lists are just for the purpose of the demo. In the future we will use the database to get the data. #
    products = [
                "This is the first product.", 
                "This is the second product.", 
                "This is the third product." , 
                "This is the fourth product."
                ]
    images = [
            "https://scamskate.com/cdn/shop/products/Scamazonshirts_1024x1024.png?v=1634931964",
            "https://scamskate.com/cdn/shop/products/Penny-Calypso_480x.jpg?v=1645207295",
            "https://scamskate.com/cdn/shop/products/20221119_165311-PhotoRoom_480x.png?v=1668901190",
            "https://scamskate.com/cdn/shop/products/fallenthegoatorangeblack-01_480x.png?v=1628790088"
            ]
    prices = [
            "€ 20,00",
            "€ 14,99",	
            "€ 29,99",
            "€ 139,00"
            ]   

    return render_template("products.html", products=products, images=images, prices=prices)

@app.route("/server/")
def server():
    # look in products.html how to use the forloop(array) correct and not making it go double. At this moment it goes double for visual purpose #
    # status is just a demo list how it could look like on the page #
    status = ["ok", "not ok"]
    services = ["order-processing-service", "user-managament-service", "product-catalog-service"]
    return render_template("server.html", utc_dt=datetime.datetime.utcnow(), status=status, services=services)

### Make requests to the other services and return the result ok or not ok ###

#def check_server_status():
    # r1 = requests.get("http://order-processing-service:5001")
    # r2 = requests.get("http://produkt-catalog-service:5004")
    # return f"order-processing-service says: {r1.text}! - user-managament-service says {r2.text} - product-catalog-service says {r3.text}" 


# Very important to disable debug mode
app.run(host="0.0.0.0", port=5002, debug=False)
