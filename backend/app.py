from flask import Flask, render_template, redirect, url_for, request, jsonify
import datetime
import json
import requests
from prometheus_flask_exporter import PrometheusMetrics
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
import os

server_port = os.environ.get("DB_PORT")
user_management = os.environ.get("USER_URL")
user_port = os.environ.get("USER_PORT")
try:
    user_port = int(user_port)
except ValueError:
    # Om konverteringen till int misslyckas
    user_port = user_port
product_catalog = os.environ.get("PRODUCT_URL")
product_port = os.environ.get("PRODUCT_PORT")
try:
    product_port = int(product_port)
except ValueError:
    # Om konverteringen till int misslyckas
    product_port = product_port
order_processing = os.environ.get("ORDER_URL")
order_port = os.environ.get("ORDER_PORT")
try:
    order_port = int(order_port)
except ValueError:
    # Om konverteringen till int misslyckas
    order_port = order_port

# Initialize Flask-Login
login_manager = LoginManager()

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Replace with a secure secret key

metrics = PrometheusMetrics(app)
metrics.info("app_info", "home-page-service", version="1.0.0")

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)


# Create a dummy User class for demonstration
class User(UserMixin):
    def __init__(self, id):
        self.id = id


# Simulate a user database (replace with your user authentication logic)
users = {"password": "password1", "user": "user1"}


@login_manager.user_loader
def load_user(user_id):
    return User(user_id)


@metrics.counter(
    "invocation_by_method",
    "Number of invocations by HTTP method",
)
def check_user_auth():
    if current_user.is_authenticated:
        user = users["user"]
    else:
        user = "false"
    return user


@app.route("/")
def hello():
    return render_template("index.html", utc_dt=datetime.datetime.utcnow())


@app.route("/admin-product/")
@login_required
def handle_products():
    user = users["user"]
    # return handle
    try:
        response = requests.get(f"http://{product_catalog}:{product_port}/api/products")
        if response.status_code == 200:
            products = json.loads(response.text)
    except requests.exceptions.RequestException as e:
        products = "Failed to fetch data"
    return render_template("admin-product.html", products=products, user=user)


@app.route("/login/", methods=["GET"])
def get_login():
    if current_user.is_authenticated:
        return redirect(url_for("handle_products"))
    return render_template("login.html")


@app.route("/lougout", methods=["GET"])
def logout():
    logout_user()
    return render_template("login.html")


@app.route("/delete/", methods=["GET"])
def delete_p():
    id = request.args.get("id")
    delete_url = f"http://{product_catalog}:{product_port}/api/product/{id}"
    response = requests.delete(delete_url)
    if response.status_code == 204:
        # The DELETE request was successful, and there's no response content.
        return redirect(url_for("handle_products"))
    elif response.status_code == 404:
        return jsonify({"error": "Product not found"})
    else:
        return jsonify({"error": "Failed to delete product"})


@app.route("/update/", methods=["POST"])
def update_p():
    newCat = []
    id = request.form["id"]
    order = request.form["updateOrder"]
    price = request.form["updatePrice"]
    img = request.form["updateImg"]
    catArray = request.form["updateCat"]
    # for x in catArray:
    #     newCat.append(x)
    # return [catArray]  # , newCat
    json_data = json.dumps(
        {"order": order, "price": price, "image": img}  # , "category": catArray
    )
    d_url = f"http://{product_catalog}:{product_port}/api/product/{id}"
    headers = {"Content-Type": "application/json"}
    response = requests.put(d_url, data=json_data, headers=headers)
    if response.status_code == 200:
        # The POST request was successful
        return redirect(url_for("handle_products"))
    else:
        return f"POST request returned a status code: {response.status_code}"
        # You can handle different status codes as needed


@app.route("/add_products/", methods=["POST"])
def post_product():
    order = request.form["name"]
    price = request.form["price"]
    img = request.form["images"]
    add_url = f"http://{product_catalog}:{product_port}/api/product"

    json_data = json.dumps({"order": order, "price": price, "image": img})
    headers = {"Content-Type": "application/json"}
    response = requests.post(add_url, data=json_data, headers=headers)
    if response.status_code == 201:
        # The POST request was successful
        return redirect(url_for("handle_products"))
    else:
        return f"POST request returned a status code: {response.status_code}"
        # You can handle different status codes as needed


@app.route("/login/", methods=["POST"])
def post_login():
    if (
        users["user"] == request.form["username"]
        and users["password"] == request.form["password"]
    ):
        user = User(request.form["username"])
        login_user(user)
        return redirect(url_for("handle_products"))
    else:
        return redirect(url_for("get_login"))


@app.route("/about/")
def about():
    return render_template("about.html")


@app.route("/products/", methods=["GET"])
def products():
    category = ["all"]
    try:
        response = requests.get(f"http://{product_catalog}:{product_port}/api/products")
        if response.status_code == 200:
            products = json.loads(response.text)
    except requests.exceptions.RequestException as e:
        products = "Failed to fetch data"

    if products != "Failed to fetch data":
        for x in products:
            for a in x["category"]:
                category.append(a)

    return render_template(
        "products.html",
        products=products,
        category=list(dict.fromkeys(category)),
        user=check_user_auth(),
    )


@app.route("/products", methods=["POST"])
def handle_category_product():
    categoryName = request.form["category"]
    if categoryName == "all":
        return redirect(url_for("products"))
    category = ["all"]
    try:
        res = requests.get(
            f"http://{product_catalog}:{product_port}/api/product_category/{categoryName}"
        )
        res_all = requests.get(f"http://{product_catalog}:{product_port}/api/products")
        if res.status_code == 200 and res_all.status_code == 200:
            products_category = json.loads(res.text)
            products_all = json.loads(res_all.text)

            for x in products_all:
                for a in x["category"]:
                    category.append(a)
            return render_template(
                "products.html",
                products=products_category,
                category=list(dict.fromkeys(category)),
                user=check_user_auth(),
            )
    except requests.exceptions.RequestException as e:
        return redirect(url_for("products"))


@app.route("/server/")
def server():
    try:
        res1 = requests.get(f"http://{product_catalog}:{product_port}")
        if res1.status_code == 200:
            r1 = res1.text
    except requests.exceptions.RequestException as e:
        r1 = "Failed to fetch data"

    try:
        res2 = requests.get(f"http://{user_management}:{user_port}")
        if res2.status_code == 200:
            r2 = res2.text
    except requests.exceptions.RequestException as e:
        r2 = "Failed to fetch data"

    try:
        res3 = requests.get(f"http://{order_processing}:{order_port}")
        if res3.status_code == 200:
            r3 = res3.text
    except requests.exceptions.RequestException as e:
        r3 = "Failed to fetch data"

    status = [
        {"name": "product-catalog-service", "status": r1},
        {"name": "user-managament-service", "status": r2},
        {"name": "order-processing-service", "status": r3},
    ]

    return render_template(
        "server.html", utc_dt=datetime.datetime.utcnow(), status=status
    )


# Very important to disable debug mode
app.run(host="0.0.0.0", port=server_port, debug=False)
