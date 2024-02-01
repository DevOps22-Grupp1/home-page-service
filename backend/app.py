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
import math


server_port = os.environ.get("SERVER_PORT")
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
metrics.info("app_info", "home-page-service", version="1.0.1")

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)


# Create a dummy User class for demonstration
class User(UserMixin):
    def __init__(self, id):
        self.id = id


# Simulate a user database (replace with your user authentication logic)
users = {"username": "", "role": "", "avatar": "", "id": ""}


@login_manager.user_loader
def load_user(user_id):
    return User(user_id)


@metrics.counter(
    "invocation_by_method",
    "Number of invocations by HTTP method",
)
def get_count_for_current_user():
    if current_user.is_authenticated:
        user_id = users["id"]
        request = requests.get(
            f"http://{order_processing}:{order_port}/api/count-products/{user_id}"
        )
        if request.status_code == 200:
            repondcount = json.loads(request.text)
            basketCount = repondcount
        else:
            basketCount = 0
    else:
        basketCount = 0
    return basketCount


def check_user_auth():
    user = {"user": "", "role": "", "image": ""}
    if current_user.is_authenticated:
        if users["username"] == "":
            logout()
            user["user"] = "false"
        else:
            user["user"] = users["username"]
            user["role"] = users["role"]
            user["image"] = users["avatar"]
    else:
        user["user"] = "false"
    return user


@app.route("/")
def hello():
    category = []
    cat_prod = []
    try:
        response = requests.get(
            f"http://{product_catalog}:{product_port}/api/products/0"
        )

        if response.status_code == 200:
            products = json.loads(response.text)
    except requests.exceptions.RequestException as e:
        products = "Failed to fetch data"

    for x in products:
        for a in x["category"]:
            category.append(a.strip())
        for x in list(dict.fromkeys(category)):
            prod_cat = requests.get(
                f"http://{product_catalog}:{product_port}/api/product_category/{x}"
            )
            m = json.loads(prod_cat.text)
            cat_prod.append(m[0])

        return render_template(
            "index.html",
            products=cat_prod,
            utc_dt=datetime.datetime.utcnow(),
            user=check_user_auth(),
            value=get_count_for_current_user(),
        )


@app.route("/subscribe", methods=["POST"])
def handling_sub():
    return render_template(
        "index.html",
        utc_dt=datetime.datetime.utcnow,
        user=check_user_auth(),
    )


@app.route("/admin-product/")
@login_required
def handle_products():
    if request.args.get("page") == None:
        page = 1
    else:
        page = int(request.args.get("page"))
    user = users["username"]
    try:
        response = requests.get(
            f"http://{product_catalog}:{product_port}/api/products/{page}"
        )
        responseCount = requests.get(
            f"http://{product_catalog}:{product_port}/api/count/all"
        )
        if response.status_code == 200:
            products = json.loads(response.text)
            count = json.loads(responseCount.text)
    except requests.exceptions.RequestException as e:
        products = "Failed to fetch data"
    return render_template(
        "admin-product.html",
        products=products,
        user=check_user_auth(),
        value=get_count_for_current_user(),
        current_page=page,
        total_page=math.ceil(count / 9),
    )


@app.route("/login/", methods=["GET"])
def get_login():
    if users["username"] == "":
        logout()
    # if current_user.is_authenticated:
    #     return redirect(url_for("products"))
    return render_template("login.html", user=check_user_auth())


@app.route("/logout", methods=["GET"])
def logout():
    logout_user()
    users["username"] = ""
    return render_template("login.html", user=check_user_auth())


@app.route("/pagination/", methods=["GET"])
def pagination():
    return request.args.get("page")


@app.route("/buy/", methods=["GET"])
def buy():
    user_id = users["id"]
    product_id = request.args.get("id")
    json_data = json.dumps({"userid": int(user_id), "productid": int(product_id)})
    d_url = f"http://{order_processing}:{order_port}/api/cart"
    headers = {"Content-Type": "application/json"}
    requests.post(d_url, data=json_data, headers=headers)
    return redirect(url_for("products"))


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
    catArray = request.form["updateCat"].split(",")
    for x in catArray:
        newCat.append(x.strip())
    json_data = json.dumps(
        {"order": order, "price": price, "image": img, "category": newCat}  #
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


@app.route("/delete_cart/", methods=["GET"])
def del_cart():
    id = request.args.get("id")
    delete_url = f"http://{order_processing}:{order_port}/api/cart/{id}"
    response = requests.delete(delete_url)
    if response.status_code == 204:
        # The DELETE request was successful, and there's no response content.
        return redirect(url_for("cart"))
    elif response.status_code == 404:
        return jsonify({"error": "Product not found"})
    else:
        return jsonify({"error": "Failed to delete product"})
    return "muu"


@app.route("/add_products/", methods=["POST"])
def post_product():
    order = request.form["name"]
    price = request.form["price"]
    img = request.form["images"]
    cat = request.form["category"]
    add_url = f"http://{product_catalog}:{product_port}/api/product"

    json_data = json.dumps(
        {"order": order, "price": price, "image": img, "category": [cat]}
    )
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
    login_url = f"http://{user_management}:{user_port}/api/login"
    add_url = f"http://{user_management}:{user_port}/api/user"
    headers = {"Content-Type": "application/json"}

    if "sign_in" in request.form:
        user = request.form["user"]
        passw = request.form["password"]
        json_data = json.dumps({"username": user, "password": passw})
        try:
            response = requests.post(login_url, data=json_data, headers=headers)
            dataresponse = json.loads(response.text)
            if len(dataresponse) == 1 and response.status_code == 200:
                user = User(dataresponse[0]["username"])
                login_user(user)
                users["username"] = dataresponse[0]["username"]
                users["id"] = dataresponse[0]["id"]
                users["role"] = dataresponse[0]["role"]
                users["avatar"] = dataresponse[0]["avatar"]
                return redirect(url_for("products"))
            else:
                return redirect(url_for("get_login"))
        except requests.exceptions.RequestException as e:
            return redirect(url_for("get_login"))
    else:
        user = request.form["username"]
        name = request.form["name"]
        passw = request.form["pass"]
        email = request.form["email"]
        avatar = request.form["avatar"]
        role = request.form["select"]
        json_data = json.dumps(
            {
                "name": name,
                "username": user,
                "password": passw,
                "avatar": avatar,
                "role": role,
                "email": email,
            }
        )

        try:
            response = requests.post(add_url, data=json_data, headers=headers)
            dataresponse = json.loads(response.text)
            if response.status_code == 201:
                json_data = json.dumps({"username": user, "password": passw})
                response = requests.post(login_url, data=json_data, headers=headers)
                dataresponse = json.loads(response.text)
                if len(dataresponse) == 1 and response.status_code == 200:
                    user = User(dataresponse[0]["username"])
                    login_user(user)
                    users["username"] = dataresponse[0]["username"]
                    users["id"] = dataresponse[0]["id"]
                    users["role"] = dataresponse[0]["role"]
                    users["avatar"] = dataresponse[0]["avatar"]
                    return redirect(url_for("products"))
                else:
                    return redirect(url_for("get_login"))
        except requests.exceptions.RequestException as e:
            return redirect(url_for("get_login"))

        return redirect(url_for("get_login"))


@app.route("/about/")
def about():
    return render_template(
        "about.html",
        user=check_user_auth(),
        value=get_count_for_current_user(),
    )


@app.route("/cart/", methods=["GET"])
@login_required
def cart():
    data = []
    price = 0
    user_id = users["id"]
    request = requests.get(
        f"http://{order_processing}:{order_port}/api/cart-user/{user_id}"
    )

    respjson = json.loads(request.text)
    for prod in respjson:
        id = prod["id"]
        prod_id = int(prod["productid"])
        prodreq = requests.get(
            f"http://{product_catalog}:{product_port}/api/product/{prod_id}"
        )
        prodjson = json.loads(prodreq.text)
        prodjson[0]["order_id"] = id
        price = price + prodjson[0]["price"]
        data.append(prodjson[0])

    return render_template(
        "cart.html",
        products=data,
        user=check_user_auth(),
        value=get_count_for_current_user(),
        price=round(price, 2),
    )


@app.route("/products", methods=["GET"])
def products():
    if request.args.get("page") == None:
        page = 1
    else:
        page = int(request.args.get("page"))

    category = ["all"]
    sel = "all"
    try:
        response = requests.get(
            f"http://{product_catalog}:{product_port}/api/products/{page}"
        )
        responseCount = requests.get(
            f"http://{product_catalog}:{product_port}/api/count/all"
        )
        res_all = requests.get(
            f"http://{product_catalog}:{product_port}/api/products/0"
        )

        if response.status_code == 200:
            count = json.loads(responseCount.text)
            products = json.loads(response.text)
            products_all = json.loads(res_all.text)
    except requests.exceptions.RequestException as e:
        products = "Failed to fetch data"

    if products != "Failed to fetch data":
        for x in products_all:
            for a in x["category"]:
                category.append(a.strip())
    return render_template(
        "products.html",
        products=products,
        category=list(dict.fromkeys(category)),
        sel=sel,
        user=check_user_auth(),
        value=get_count_for_current_user(),
        current_page=page,
        total_page=math.ceil(count / 9),
    )


@app.route("/payment", methods=["GET"])
def buy_products():
    data = []
    price = 0
    user_id = users["id"]
    request = requests.get(
        f"http://{order_processing}:{order_port}/api/cart-user/{user_id}"
    )

    respjson = json.loads(request.text)
    for prod in respjson:
        id = prod["id"]
        prod_id = int(prod["productid"])
        prodreq = requests.get(
            f"http://{product_catalog}:{product_port}/api/product/{prod_id}"
        )
        prodjson = json.loads(prodreq.text)
        prodjson[0]["order_id"] = id
        price = price + prodjson[0]["price"]
        data.append(prodjson[0])

    json_data = json.dumps(
        {
            "userid": int(user_id),
            "history": data,
            "time": str(datetime.datetime.utcnow()),
            "price": price,
        }
    )
    d_url = f"http://{order_processing}:{order_port}/api/order"
    headers = {"Content-Type": "application/json"}
    response = requests.post(d_url, data=json_data, headers=headers)
    delete_url = f"http://{order_processing}:{order_port}/api/cart/{user_id}"
    response = requests.delete(delete_url)
    if response.status_code == 204:

        return render_template(
            "checkout.html",
            user=check_user_auth(),
            value=get_count_for_current_user(),
        )


@app.route("/products", methods=["POST"])
def handle_category_product():
    categoryName = request.form["category"]
    sel = categoryName
    page = 1
    if categoryName == "all" or categoryName == "none-all":
        return redirect(url_for("products"))
    category = ["all"]
    try:
        res = requests.get(
            f"http://{product_catalog}:{product_port}/api/product_category/{categoryName}"
        )
        res_all = requests.get(
            f"http://{product_catalog}:{product_port}/api/products/0"
        )
        responseCount = requests.get(
            f"http://{product_catalog}:{product_port}/api/count/{categoryName}"
        )
        if "," in sel:
            sel = sel.split(",")[1]

        if res.status_code == 200 and res_all.status_code == 200:
            products_category = json.loads(res.text)
            products_all = json.loads(res_all.text)
            count = json.loads(responseCount.text)
            for x in products_all:
                for a in x["category"]:
                    category.append(a)
            return render_template(
                "products.html",
                products=products_category,
                category=list(dict.fromkeys(category)),
                sel=sel,
                user=check_user_auth(),
                value=get_count_for_current_user(),
                current_page=page,
                total_page=math.ceil(count / 9),
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
        "server.html",
        utc_dt=datetime.datetime.utcnow(),
        status=status,
        user=check_user_auth(),
        value=get_count_for_current_user(),
    )


# Very important to disable debug mode
app.run(host="0.0.0.0", port=server_port, debug=False, use_reloader=False)
