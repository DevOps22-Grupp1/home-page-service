from flask import Flask, render_template, redirect, url_for, request, jsonify, abort, session
from functools import wraps
from werkzeug.middleware.proxy_fix import ProxyFix
import datetime
import json
import requests
from prometheus_flask_exporter import PrometheusMetrics
import os
import math
import time

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

app = Flask(__name__)
# Behind a proxy on a sub-path (e.g. Traefik on /scamazon): X-Forwarded-Prefix makes url_for()
# build links with the prefix. Without a proxy it changes nothing.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.secret_key = os.environ.get("SECRET_KEY", "your_secret_key")  # Set SECRET_KEY in production
# Strict: the browser never sends the session cookie on a request from another site, so a link or
# form elsewhere cannot buy, delete or change products in a logged-in visitor's name.
app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE") == "1"

# Admin logs in with the magic link (Telegram) in the shared n8n login flow; customers with a
# username and password from user-management-service. No admin password exists anywhere.
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "https://jarllindquist.com/n8n/webhook")
MAGIC_LINK_APP = os.environ.get("MAGIC_LINK_APP", "scamazon-admin")

# The avatars a customer picks from at sign-up, in static/avatars/ (drawn by tools/avatars/).
# Only these names are stored; an image from another site would load on every page.
AVATARS = [f"avatar-{n}.svg" for n in range(1, 9)]
# The public demo account (user-management-service creates it); the login page shows it
DEMO_USERNAME = os.environ.get("DEMO_USERNAME", "")
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "")


def avatar_url(name: str) -> str:
    """Older accounts hold a URL from anywhere; they get the first avatar instead."""
    return url_for("static", filename="avatars/" + (name if name in AVATARS else AVATARS[0]))


@app.context_processor
def login_page_values() -> dict:
    return {"avatars": AVATARS, "demo_username": DEMO_USERNAME, "demo_password": DEMO_PASSWORD}

metrics = PrometheusMetrics(app)
metrics.info("app_info", "home-page-service", version="1.0.1")


# Who is logged in lives in each visitor's own (signed) session cookie: session["customer"] for a
# customer, session["admin_session"] for the admin's magic-link session.
def current_customer() -> dict | None:
    return session.get("customer")


# Answers from n8n's session-check, per magic-link session: {session_id: (valid, checked_at)}
_admin_checks = {}


def is_admin() -> bool:
    session_id = session.get("admin_session")
    if not session_id:
        return False
    valid, checked_at = _admin_checks.get(session_id, (False, 0))
    # A yes is trusted for a minute, a no for ten seconds; n8n renews the session on each check
    if time.time() - checked_at < (60 if valid else 10):
        return valid
    try:
        response = requests.post(
            f"{N8N_WEBHOOK_URL}/session-check",
            json={"app": MAGIC_LINK_APP},
            headers={"X-Admin-Session": session_id},
            timeout=5,
        )
        valid = response.status_code == 200 and response.json().get("valid") is True
    except (requests.exceptions.RequestException, ValueError):
        valid = False  # n8n unreachable: no admin
    _admin_checks[session_id] = (valid, time.time())
    if not valid:
        session.pop("admin_session", None)
    return valid


def customer_route(view):
    """Cart, buying and checkout: a logged-in customer."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_customer():
            return redirect(url_for("get_login"))
        return view(*args, **kwargs)

    return wrapper


def admin_route(view):
    """Adding, changing and deleting products: the admin, logged in with the magic link."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if not is_admin():
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)

    return wrapper


def log_in_customer(user: dict) -> None:
    session.clear()
    session["customer"] = {
        "id": user["id"],
        "username": user["username"],
        "avatar": user.get("avatar", ""),
    }


@metrics.counter(
    "invocation_by_method",
    "Number of invocations by HTTP method",
)
def get_count_for_current_user() -> int:
    customer = current_customer()
    if customer:
        user_id = customer["id"]
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


def check_user_auth() -> dict:
    """What the templates need: user is the name, or "false" when nobody is logged in."""
    customer = current_customer()
    if customer:
        return {"user": customer["username"], "role": "customer", "image": avatar_url(customer["avatar"])}
    if is_admin():
        return {"user": "admin", "role": "admin", "image": ""}
    return {"user": "false", "role": "", "image": ""}


@app.route("/")
def index() -> tuple:
    return render_template("landing.html")


@app.route("/home")
def hello() -> tuple:
    category = []
    cat_prod = []
    try:
        response = requests.get(
            f"http://{product_catalog}:{product_port}/api/products/0"
        )

        if response.status_code == 200:
            products = json.loads(response.text)
            for x in products:
                for a in x["category"]:
                    if a.strip() not in category:
                        category.append(a.strip())

            for x in category:
                prod_cat = requests.get(
                    f"http://{product_catalog}:{product_port}/api/product_category/{x}"
                )
                m = json.loads(prod_cat.text)
                cat_prod.append(m[0])
    except requests.exceptions.RequestException as e:
        products = "Failed to fetch data"

    return render_template(
        "index.html",
        products=cat_prod,
        utc_dt=datetime.datetime.utcnow(),
        user=check_user_auth(),
        value=get_count_for_current_user(),
    )


@app.route("/subscribe", methods=["POST"])
def handling_sub() -> tuple:
    return render_template(
        "index.html",
        utc_dt=datetime.datetime.utcnow,
        user=check_user_auth(),
    )


@app.route("/admin-product/")
@admin_route
def handle_products() -> tuple:
    if request.args.get("page") is None:
        page = 1
    else:
        page = int(request.args.get("page"))
    products = "Failed to fetch data"
    count = 0
    try:
        response = requests.get(
            f"http://{product_catalog}:{product_port}/api/products/{page}"
        )
        responseCount = requests.get(
            f"http://{product_catalog}:{product_port}/api/count/all"
        )
        if response.status_code == 200:
            count = json.loads(responseCount.text)
            products = json.loads(response.text)
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
def get_login() -> tuple:
    return render_template("login.html", user=check_user_auth())


@app.route("/logout", methods=["GET"])
def logout() -> tuple:
    session.clear()
    return render_template("login.html", user=check_user_auth())


@app.route("/admin-login/", methods=["GET"])
def admin_login() -> tuple:
    if is_admin():
        return redirect(url_for("handle_products"))
    return render_template("admin-login.html", user=check_user_auth())


# Sends the magic link to Telegram; the page then polls admin_login_status
@app.route("/admin-login/", methods=["POST"])
def admin_login_request() -> tuple:
    try:
        response = requests.post(
            f"{N8N_WEBHOOK_URL}/request-magic-link", json={"app": MAGIC_LINK_APP}, timeout=10
        )
        if response.status_code == 429:
            return jsonify({"error": "too_many"}), 429
        session_id = response.json().get("sessionId")
    except (requests.exceptions.RequestException, ValueError):
        session_id = None
    if not session_id:
        return jsonify({"error": "failed"}), 502
    session["pending_admin_session"] = session_id
    return jsonify({"sent": True})


@app.route("/admin-login/status", methods=["GET"])
def admin_login_status() -> tuple:
    session_id = session.get("pending_admin_session")
    if not session_id:
        return jsonify({"authenticated": False, "error": "no_request"}), 400
    try:
        response = requests.post(
            f"{N8N_WEBHOOK_URL}/check-login-status", json={"sessionId": session_id}, timeout=10
        )
        authenticated = response.json().get("authenticated") is True
    except (requests.exceptions.RequestException, ValueError):
        authenticated = False
    if authenticated:
        # The admin is not also a customer: a fresh session holding only the admin login
        session.clear()
        session["admin_session"] = session_id
    return jsonify({"authenticated": authenticated})


@app.route("/pagination/", methods=["GET"])
def pagination() -> str:
    return request.args.get("page")


@app.route("/buy/", methods=["GET"])
@customer_route
def buy() -> tuple:
    user_page = request.args.get("page", 1)
    user_id = current_customer()["id"]
    product_id = request.args.get("id")
    json_data = json.dumps({"userid": int(user_id), "productid": int(product_id)})
    d_url = f"http://{order_processing}:{order_port}/api/cart"
    headers = {"Content-Type": "application/json"}
    requests.post(d_url, data=json_data, headers=headers)
    return redirect(url_for("products", page=user_page))
    # page=user_page


@app.route("/delete/", methods=["GET"])
@admin_route
def delete_p() -> tuple:
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
@admin_route
def update_p() -> tuple:
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
@customer_route
def del_cart() -> tuple:
    p_id = request.args.get("p_id")
    cart_id = request.args.get("c_id")
    # Only a row in this customer's own cart, whatever ids the link carries
    user_id = current_customer()["id"]
    own = requests.get(f"http://{order_processing}:{order_port}/api/cart-user/{user_id}")
    if not any(str(row["id"]) == str(cart_id) for row in json.loads(own.text)):
        abort(404)
    delete_url = f"http://{order_processing}:{order_port}/api/cart/{cart_id}/{p_id}"
    response = requests.delete(delete_url)
    if response.status_code == 204:
        # The DELETE request was successful, and there's no response content.
        return redirect(url_for("cart"))
    elif response.status_code == 404:
        return jsonify({"error": "Product not found"})
    else:
        return jsonify({"error": "Failed to delete product"})


@app.route("/add_products/", methods=["POST"])
@admin_route
def post_product() -> tuple:
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


# {
# "password": "lC2)Pug$Dsq*8b|6",  password1
# "username": "emclinden0" user1
# }


@app.route("/login/", methods=["POST"])
def post_login() -> tuple:
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
                log_in_customer(dataresponse[0])
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
        avatar = request.form.get("avatar")
        if avatar not in AVATARS:
            avatar = AVATARS[0]
        # No role: user-management-service makes every new account a customer
        json_data = json.dumps(
            {
                "name": name,
                "username": user,
                "password": passw,
                "avatar": avatar,
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
                    log_in_customer(dataresponse[0])
                    return redirect(url_for("products"))
                else:
                    return redirect(url_for("get_login"))
        except requests.exceptions.RequestException as e:
            return redirect(url_for("get_login"))

        return redirect(url_for("get_login"))


# The customer's own account: avatar, name and email, password, deleting the account. The id is
# always the logged-in customer's, from the session; the forms carry none.
def user_url(path: str = "") -> str:
    return f"http://{user_management}:{user_port}/api/user/{current_customer()['id']}{path}"


def is_demo_customer() -> bool:
    return bool(DEMO_USERNAME) and current_customer()["username"] == DEMO_USERNAME


@app.route("/account/", methods=["GET"])
@customer_route
def account() -> tuple:
    try:
        response = requests.get(user_url("/profile"))
        profile = response.json() if response.status_code == 200 else None
    except (requests.exceptions.RequestException, ValueError):
        profile = None
    if profile is None:
        # The account is gone (deleted elsewhere): log out
        session.clear()
        return redirect(url_for("get_login"))
    return render_template(
        "account.html",
        profile=profile,
        current_avatar=profile.get("avatar") if profile.get("avatar") in AVATARS else AVATARS[0],
        is_demo=is_demo_customer(),
        message=request.args.get("message", ""),
        user=check_user_auth(),
        value=get_count_for_current_user(),
    )


@app.route("/account/profile", methods=["POST"])
@customer_route
def account_profile() -> tuple:
    avatar = request.form.get("avatar")
    if avatar not in AVATARS:
        avatar = AVATARS[0]
    fields = {"avatar": avatar}
    # The demo account is shared: everyone may pick its robot, but its name stays
    if not is_demo_customer():
        fields["name"] = request.form.get("name", "").strip()
        fields["email"] = request.form.get("email", "").strip()
        if not fields["name"] or not fields["email"]:
            return redirect(url_for("account", message="Name and email are required."))
    response = requests.put(user_url(), json=fields)
    if response.status_code != 200:
        return redirect(url_for("account", message="Could not save. Try again."))
    session["customer"] = {**current_customer(), "avatar": avatar}
    return redirect(url_for("account", message="Saved."))


@app.route("/account/password", methods=["POST"])
@customer_route
def account_password() -> tuple:
    if is_demo_customer():
        return redirect(url_for("account", message="The demo account's password stays the same."))
    new = request.form.get("new", "")
    if not new:
        return redirect(url_for("account", message="Type a new password."))
    if new != request.form.get("repeat", ""):
        return redirect(url_for("account", message="The new passwords are not the same."))
    response = requests.post(
        user_url("/password"), json={"current": request.form.get("current", ""), "new": new}
    )
    if response.status_code == 403:
        return redirect(url_for("account", message="The current password is wrong."))
    if response.status_code != 200:
        return redirect(url_for("account", message="Could not change the password. Try again."))
    return redirect(url_for("account", message="Password changed."))


@app.route("/account/delete", methods=["POST"])
@customer_route
def account_delete() -> tuple:
    if is_demo_customer():
        return redirect(url_for("account", message="The demo account cannot be deleted."))
    customer = current_customer()
    # The password again, so a forgotten open session cannot delete the account
    check = requests.post(
        f"http://{user_management}:{user_port}/api/login",
        json={"username": customer["username"], "password": request.form.get("password", "")},
    )
    if check.status_code != 200 or len(check.json()) != 1:
        return redirect(url_for("account", message="The password is wrong; the account is kept."))
    requests.delete(f"http://{order_processing}:{order_port}/api/cart/{customer['id']}")
    response = requests.delete(user_url())
    if response.status_code != 200:
        return redirect(url_for("account", message="Could not delete the account. Try again."))
    session.clear()
    return redirect(url_for("get_login"))


@app.route("/about/")
def about() -> tuple:
    return render_template(
        "about.html",
        user=check_user_auth(),
        value=get_count_for_current_user(),
    )


@app.route("/cart/", methods=["GET"])
@customer_route
def cart() -> tuple:
    data = []
    price = 0
    user_id = current_customer()["id"]
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


@app.route("/products/", methods=["GET"])
def products() -> tuple:
    if request.args.get("page") is None:
        page = 1
    else:
        page = int(request.args.get("page"))

    category = ["all"]
    sel = "all"
    products = "Failed to fetch data"
    products_all = []
    count = 0
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


@app.route("/products", methods=["POST"])
def handle_category_product() -> tuple:
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


@app.route("/payment", methods=["GET"])
@customer_route
def buy_products() -> tuple:
    data = []
    price = 0
    user_id = current_customer()["id"]
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
            "time": str(datetime.datetime.now()),
            "price": price,
        }
    )

    d_url = f"http://{order_processing}:{order_port}/api/order"
    headers = {"Content-Type": "application/json"}
    response = requests.post(d_url, data=json_data, headers=headers)
    delete_url = f"http://{order_processing}:{order_port}/api/cart/{user_id}"
    responseDelete = requests.delete(delete_url)

    if response.status_code == 201 and responseDelete.status_code == 204:
        return render_template(
            "checkout.html",
            user=check_user_auth(),
            value=get_count_for_current_user(),
        )


@app.route("/server/")
def server() -> tuple:

    print(f"http://{product_catalog}:{product_port}", "product handling")
    print(f"http://{user_management}:{user_port}", "user handling")
    print(f"http://{order_processing}:{order_port}", "order processing")

    r1 = r2 = r3 = "Failed to fetch data"
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
