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
import threading
from collections import deque, Counter
import xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_HALF_UP

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


# How long customer accounts are kept; the janitor in the deploy deletes older ones (0 = kept)
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "0") or 0)


@app.context_processor
def login_page_values() -> dict:
    return {"avatars": AVATARS, "demo_username": DEMO_USERNAME, "demo_password": DEMO_PASSWORD,
            "retention_days": RETENTION_DAYS}


# Prices are stored in euro. A visitor picks the currency they are shown in; the amounts are
# converted with the European Central Bank's daily reference rates (no key needed), fetched at
# most twice a day. If the ECB cannot be reached, the last rates or these fallbacks are used.
CURRENCIES = {
    # code: (symbol, symbol first, thousands separator, decimal separator)
    "EUR": ("€", True, ",", "."),
    "SEK": ("kr", False, " ", ","),
    "USD": ("$", True, ",", "."),
    "GBP": ("£", True, ",", "."),
}
FALLBACK_RATES = {"EUR": Decimal("1"), "SEK": Decimal("11.2"), "USD": Decimal("1.08"), "GBP": Decimal("0.85")}
ECB_RATES_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
_rates = {"rates": dict(FALLBACK_RATES), "date": "", "fetched_at": 0.0}


def exchange_rates() -> dict:
    if time.time() - _rates["fetched_at"] > 12 * 3600:
        _rates["fetched_at"] = time.time()  # also after a failure: try again in 12 hours
        # Any failure keeps the rates there are: prices must never break a page
        try:
            response = requests.get(ECB_RATES_URL, timeout=5)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            rates = {"EUR": Decimal("1")}
            for cube in root.iter():
                if cube.get("currency") in CURRENCIES:
                    rates[cube.get("currency")] = Decimal(cube.get("rate"))
                if cube.get("time"):
                    _rates["date"] = cube.get("time")
            if set(rates) == set(CURRENCIES):
                _rates["rates"] = rates
        except Exception:
            pass
    return _rates


def current_currency() -> str:
    code = session.get("currency", "EUR")
    return code if code in CURRENCIES else "EUR"


def euro_amount(value) -> Decimal | None:
    """A stored price as a number; None for one that is not (older products may hold text)."""
    try:
        amount = Decimal(str(value).strip())
    except ArithmeticError:
        return None
    return amount if amount.is_finite() else None


def to_currency(euros, code: str) -> Decimal:
    amount = Decimal(str(euros)) * exchange_rates()["rates"][code]
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def admin_price(text: str) -> float | None:
    """A price from the admin form, in euro: "399.99" or "399,99". Stored as a number, so the
    shop can convert and add it up; None when it is not a price."""
    amount = euro_amount(text.replace(",", "."))
    if amount is None or amount < 0:
        return None
    return float(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@app.template_filter("money")
def money(euros) -> str:
    """A price in euro, shown in the visitor's currency: €399.99, 4 479,89 kr, $431.99."""
    amount = euro_amount(euros)
    if amount is None:
        return str(euros)  # shown as stored rather than breaking the page
    code = current_currency()
    return format_amount(to_currency(amount, code), code)


@app.template_filter("euro")
def euro(amount) -> str:
    """A stored euro amount as it was paid, whatever currency the visitor has picked now."""
    return format_amount(amount, "EUR")


def format_amount(amount, code: str) -> str:
    """An amount already in a currency, written the way that currency is: 4 479,89 kr."""
    value = euro_amount(amount)
    if value is None or code not in CURRENCIES:
        return f"{amount} {code}"
    symbol, first, thousands, decimal = CURRENCIES[code]
    whole, cents = f"{value:,.2f}".split(".")
    number = whole.replace(",", thousands) + decimal + cents
    return f"{symbol}{number}" if first else f"{number} {symbol}"


@app.context_processor
def currency_values() -> dict:
    return {"currencies": CURRENCIES, "currency": current_currency(), "rates_date": exchange_rates()["date"]}


def back_to_page() -> tuple:
    """Back to the page the visitor was on (a path below the prefix), but only a page on this site."""
    back = request.form.get("next", "")
    if not back.startswith("/") or back.startswith("//"):
        back = "/products/"
    return redirect(request.script_root + back)


@app.route("/currency", methods=["POST"])
def set_currency() -> tuple:
    code = request.form.get("currency", "EUR")
    if code in CURRENCIES:
        session["currency"] = code
    return back_to_page()


# Five designs on the same app. Playful, dark, clean and terminal share the templates in templates/modern/
# and differ in modern.css only (data-style on <body>); classic is templates/, the group's 2023
# design with what was added since. A page the modern templates do not have yet is shown in the
# classic one.
THEMES = {"playful": "Playful", "dark": "Dark", "clean": "Clean", "terminal": "Terminal", "classic": "Classic (2023)"}
THEME_ALIASES = {"new": "playful"}  # the name the first new design had
DEFAULT_THEME = THEME_ALIASES.get(os.environ.get("DEFAULT_THEME", ""), os.environ.get("DEFAULT_THEME", ""))
if DEFAULT_THEME not in THEMES:
    DEFAULT_THEME = "playful"
MODERN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "modern")
MODERN_PAGES = set(os.listdir(MODERN_DIR)) if os.path.isdir(MODERN_DIR) else set()


def current_theme() -> str:
    theme = session.get("theme", DEFAULT_THEME)
    theme = THEME_ALIASES.get(theme, theme)
    return theme if theme in THEMES else DEFAULT_THEME


def render(name: str, **context) -> str:
    if current_theme() != "classic" and name in MODERN_PAGES:
        name = "modern/" + name
    return render_template(name, **context)


@app.context_processor
def theme_values() -> dict:
    return {"theme": current_theme(), "themes": THEMES}


# The dark patterns the modern designs use on purpose, and what "Reveal the tricks" says about
# each. The pages mark them with data-trick="<key>"; /tricks/ explains them all.
TRICKS = {
    "countdown": (
        "False urgency",
        "The countdown starts over every time the page loads. Nothing ends: the clock is there "
        "to rush you past comparing prices.",
    ),
    "viewers": (
        "Fake social proof",
        "The number of people \"viewing this\" is made up; it changes with the minute. Other "
        "people's interest makes a thing feel worth having.",
    ),
    "scarcity": (
        "False scarcity",
        "\"LAST ONE*\" on a product that never sells out. Fear of missing out beats a careful "
        "decision.",
    ),
    "anchor": (
        "Fake reference price",
        "The struck-through price is simply three times the real one. A big \"was\" price makes "
        "any price look like a bargain.",
    ),
    "preselected": (
        "Sneak into basket",
        "The add-on is ticked before you look, and it is added to the order. Opt-out extras rely "
        "on you not reading every line.",
    ),
    "confirmshaming": (
        "Confirmshaming",
        "The way to say no is worded to make you feel silly, so saying yes feels like the "
        "sensible choice.",
    ),
    "reviews": (
        "Fake reviews",
        "Every review is five stars, written by the shop's own robots and posted the same day. "
        "Reviews you cannot trace to a real buyer tell you nothing.",
    ),
}
PROTECTION_NAME = "Scam Protection Plus"
PROTECTION_FEE = Decimal("4.99")

# The robots who review everything (a trick: see "reviews" above). Each review is picked by the
# product's id, so a product always shows the same ones.
REVIEWERS = [
    "Totally Real Customer", "Not A Bot 3000", "Human Person", "Verified Buyer*",
    "Five Star Fan", "Satisfied Shopper", "Definitely Not Staff", "The CEO's Mom",
]
REVIEW_TEXTS = [
    "Best purchase of my life. Would buy again, and again, and again.",
    "Arrived in perfect condition, as far as I can tell. Five stars.",
    "I was sceptical at first. Then I read the other reviews.",
    "My whole family loves it. My whole family is also robots.",
    "Customer service answered in under a nanosecond.",
    "Cheaper than anywhere else, according to the struck-through price.",
    "Exactly as described. I did not read the description.",
    "I bought three. The countdown was very convincing.",
]


def reviews_for(product_id) -> list:
    try:
        seed = int(product_id)
    except (TypeError, ValueError):
        seed = 0
    count = 3 + seed % 3
    return [
        {
            "name": REVIEWERS[(seed + i * 3) % len(REVIEWERS)],
            "avatar": AVATARS[(seed + i * 5) % len(AVATARS)],
            "text": REVIEW_TEXTS[(seed * 2 + i) % len(REVIEW_TEXTS)],
            "stars": 5,
        }
        for i in range(count)
    ]


def viewers_now(product_id) -> int:
    """The made-up "people viewing this": the same for a product within a minute."""
    try:
        seed = int(product_id)
    except (TypeError, ValueError):
        seed = 0
    return 3 + (seed * 7 + int(time.time() // 60)) % 23


@app.context_processor
def trick_values() -> dict:
    return {
        "tricks": TRICKS,
        "reveal": session.get("reveal", False),
        "viewers_now": viewers_now,
        "protection_name": PROTECTION_NAME,
        "protection_fee": PROTECTION_FEE,
    }


@app.route("/tricks", methods=["POST"])
def toggle_tricks() -> tuple:
    session["reveal"] = not session.get("reveal", False)
    return back_to_page()


@app.route("/tricks/")
def tricks_page() -> tuple:
    return render("tricks.html", user=check_user_auth(), value=get_count_for_current_user())


@app.route("/theme", methods=["POST"])
def set_theme() -> tuple:
    theme = request.form.get("theme", "")
    theme = THEME_ALIASES.get(theme, theme)
    if theme in THEMES:
        session["theme"] = theme
    return back_to_page()

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


def clear_login() -> None:
    """Forgets who is logged in (a fresh session), but keeps the visitor's choices: design,
    currency and whether the tricks are revealed are not part of anyone's login."""
    kept = {key: session[key] for key in ("theme", "currency", "reveal") if key in session}
    session.clear()
    session.update(kept)


def log_in_customer(user: dict) -> None:
    clear_login()
    session["customer"] = {
        "id": user["id"],
        "username": user["username"],
        "avatar": user.get("avatar", ""),
    }


def empty_cart(rows: list) -> bool:
    """Deletes the given cart rows (from /api/cart-user/<id>) one by one: order-processing has
    no route that empties a whole cart. True when every row is gone."""
    ok = True
    for row in rows:
        response = requests.delete(
            f"http://{order_processing}:{order_port}/api/cart/{row['id']}/{row['productid']}"
        )
        ok = ok and response.status_code == 204
    return ok


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
    # The fade-in intro belongs to the classic design; the new one opens on the shop
    if current_theme() != "classic":
        return redirect(url_for("hello"))
    return render("landing.html")


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

    return render(
        "index.html",
        products=cat_prod,
        utc_dt=datetime.datetime.utcnow(),
        user=check_user_auth(),
        value=get_count_for_current_user(),
    )


@app.route("/subscribe", methods=["POST"])
def handling_sub() -> tuple:
    return render(
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
    return render(
        "admin-product.html",
        products=products,
        user=check_user_auth(),
        value=get_count_for_current_user(),
        current_page=page,
        total_page=math.ceil(count / 9),
    )


@app.route("/login/", methods=["GET"])
def get_login() -> tuple:
    return render("login.html", message=request.args.get("message", ""), user=check_user_auth())


@app.route("/logout", methods=["GET"])
def logout() -> tuple:
    clear_login()
    return render("login.html", user=check_user_auth())


@app.route("/admin-login/", methods=["GET"])
def admin_login() -> tuple:
    if is_admin():
        return redirect(url_for("admin_dashboard"))
    return render("admin-login.html", user=check_user_auth())


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
        clear_login()
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
    price = admin_price(request.form["updatePrice"])
    if price is None:
        return "The price must be a number of euros, like 399.99.", 400
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
    price = admin_price(request.form["price"])
    if price is None:
        return "The price must be a number of euros, like 399.99.", 400
    img = request.form["images"]
    cat = request.form.get("category", "").strip() or "other"
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


# ---------- Limits: the shop is public and anyone may sign up ----------
# In memory, per client address (ProxyFix gives the visitor's address behind Traefik) and for
# everyone together: when a window is full, the request is refused until the oldest one in it
# is older than the window.
LIMITS = {
    "signup_ip": (int(os.environ.get("SIGNUP_PER_IP_PER_HOUR", "3")), 3600),
    "signup_all": (int(os.environ.get("SIGNUPS_PER_HOUR", "30")), 3600),
    "login_fail_ip": (int(os.environ.get("FAILED_LOGINS_PER_IP", "10")), 900),
}
_hits = {}
_hits_lock = threading.Lock()


def limited(kind: str, key: str = "") -> bool:
    """True if the window for this kind (and key) is full; does not count anything."""
    limit, window = LIMITS[kind]
    now = time.time()
    with _hits_lock:
        times = _hits.setdefault((kind, key), deque())
        while times and now - times[0] > window:
            times.popleft()
        return len(times) >= limit


def count_hit(kind: str, key: str = "") -> None:
    with _hits_lock:
        _hits.setdefault((kind, key), deque()).append(time.time())


def login_page(message: str) -> tuple:
    return redirect(url_for("get_login", message=message))


@app.route("/login/", methods=["POST"])
def post_login() -> tuple:
    login_url = f"http://{user_management}:{user_port}/api/login"
    add_url = f"http://{user_management}:{user_port}/api/user"
    headers = {"Content-Type": "application/json"}
    client = request.remote_addr or "unknown"

    if "sign_in" in request.form:
        if limited("login_fail_ip", client):
            return login_page("Too many wrong passwords. Wait a quarter of an hour and try again.")
        user = request.form["user"]
        passw = request.form["password"]
        json_data = json.dumps({"username": user, "password": passw})
        try:
            response = requests.post(login_url, data=json_data, headers=headers)
            dataresponse = json.loads(response.text)
            if len(dataresponse) == 1 and response.status_code == 200:
                log_in_customer(dataresponse[0])
                return redirect(url_for("products"))
            count_hit("login_fail_ip", client)
            return login_page("Wrong username or password.")
        except (requests.exceptions.RequestException, ValueError):
            return login_page("The account service did not answer. Try again in a moment.")

    if limited("signup_ip", client):
        return login_page("You have made a few accounts already. Try again in an hour, or use the demo account.")
    if limited("signup_all"):
        return login_page("Lots of new accounts right now. Try again later, or use the demo account.")
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
        if response.status_code != 201:
            reason = dataresponse.get("message", "") if isinstance(dataresponse, dict) else ""
            return login_page(f"The account was not created. {reason}".strip())
        count_hit("signup_ip", client)
        count_hit("signup_all")
        json_data = json.dumps({"username": user, "password": passw})
        response = requests.post(login_url, data=json_data, headers=headers)
        dataresponse = json.loads(response.text)
        if len(dataresponse) == 1 and response.status_code == 200:
            log_in_customer(dataresponse[0])
            return redirect(url_for("products"))
        return login_page("The account was created; log in with it.")
    except (requests.exceptions.RequestException, ValueError):
        return login_page("The account service did not answer. Try again in a moment.")


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
        clear_login()
        return redirect(url_for("get_login"))
    return render(
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
    rows = requests.get(f"http://{order_processing}:{order_port}/api/cart-user/{customer['id']}")
    empty_cart(json.loads(rows.text))
    response = requests.delete(user_url())
    if response.status_code != 200:
        return redirect(url_for("account", message="Could not delete the account. Try again."))
    clear_login()
    return redirect(url_for("get_login"))


@app.route("/product/<int:product_id>/")
def product_page(product_id: int) -> tuple:
    try:
        response = requests.get(f"http://{product_catalog}:{product_port}/api/product/{product_id}")
        found = response.json() if response.status_code == 200 else []
    except (requests.exceptions.RequestException, ValueError):
        found = []
    if not found:
        abort(404)
    product = found[0]
    # "Customers also bought": others in the same category, at most four
    related = []
    try:
        everything = requests.get(f"http://{product_catalog}:{product_port}/api/products/0").json()
        categories = {c.strip() for c in product.get("category", [])}
        related = [
            p for p in everything
            if p.get("id") != product.get("id") and categories & {c.strip() for c in p.get("category", [])}
        ][:4]
    except (requests.exceptions.RequestException, ValueError, TypeError, AttributeError):
        related = []
    return render(
        "product.html",
        product=product,
        reviews=reviews_for(product.get("id")),
        related=related,
        today=datetime.date.today().isoformat(),
        user=check_user_auth(),
        value=get_count_for_current_user(),
    )


@app.route("/orders/")
@customer_route
def orders() -> tuple:
    """The customer's own orders, newest first, in the currency each was paid in."""
    user_id = current_customer()["id"]
    try:
        response = requests.get(f"http://{order_processing}:{order_port}/api/order-user/{user_id}")
        found = response.json() if response.status_code == 200 else []
    except (requests.exceptions.RequestException, ValueError):
        found = []
    if not isinstance(found, list):
        found = []
    found = sorted((o for o in found if isinstance(o, dict)), key=lambda o: o.get("id", 0), reverse=True)
    for order in found:
        # Orders from before the currencies were in euro only
        order.setdefault("currency", "EUR")
        if "price_in_currency" not in order:
            order["price_in_currency"] = f"{euro_amount(order.get('price')) or Decimal('0'):.2f}"
        order["shown_total"] = format_amount(order["price_in_currency"], order["currency"])
        order["when"] = str(order.get("time", ""))[:16]
    return render("orders.html", orders=found, user=check_user_auth(), value=get_count_for_current_user())


@app.route("/about/")
def about() -> tuple:
    return render(
        "about.html",
        user=check_user_auth(),
        value=get_count_for_current_user(),
    )


@app.route("/cart/", methods=["GET"])
@customer_route
def cart() -> tuple:
    data = []
    price = Decimal("0")
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
        price = price + (euro_amount(prodjson[0]["price"]) or Decimal("0"))
        data.append(prodjson[0])
    return render(
        "cart.html",
        products=data,
        user=check_user_auth(),
        value=get_count_for_current_user(),
        price=price,
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
    return render(
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
            return render(
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


@app.route("/payment", methods=["GET", "POST"])
@customer_route
def buy_products() -> tuple:
    data = []
    price = Decimal("0")
    user_id = current_customer()["id"]
    # The modern cart posts its form with the pre-ticked add-on (a dark pattern, see TRICKS);
    # the classic cart's plain link pays without it
    protection = request.method == "POST" and request.form.get("protection") == "on"
    cart_response = requests.get(
        f"http://{order_processing}:{order_port}/api/cart-user/{user_id}"
    )

    respjson = json.loads(cart_response.text)
    if not respjson:
        return redirect(url_for("cart"))  # nothing to pay for
    for prod in respjson:
        id = prod["id"]
        prod_id = int(prod["productid"])
        prodreq = requests.get(
            f"http://{product_catalog}:{product_port}/api/product/{prod_id}"
        )
        prodjson = json.loads(prodreq.text)
        prodjson[0]["order_id"] = id
        price = price + (euro_amount(prodjson[0]["price"]) or Decimal("0"))
        data.append(prodjson[0])
    extras = []
    if protection:
        price = price + PROTECTION_FEE
        extras.append({"name": PROTECTION_NAME, "price": float(PROTECTION_FEE)})

    json_data = json.dumps(
        {
            "userid": int(user_id),
            "history": data,
            "extras": extras,
            "time": str(datetime.datetime.now()),
            # The total in euro, as before, and what the customer saw and paid in
            "price": float(price),
            "currency": current_currency(),
            "rate": str(exchange_rates()["rates"][current_currency()]),
            "price_in_currency": str(to_currency(price, current_currency())),
        }
    )

    d_url = f"http://{order_processing}:{order_port}/api/order"
    headers = {"Content-Type": "application/json"}
    response = requests.post(d_url, data=json_data, headers=headers)

    if response.status_code == 201 and empty_cart(respjson):
        return render(
            "checkout.html",
            user=check_user_auth(),
            value=get_count_for_current_user(),
        )
    # The order did not go through: back to the cart instead of an error page
    return redirect(url_for("cart"))


# ---------- Service status: response times and history ----------
# Every probe asks each service's root and times it. The last 120 probes per service are kept in
# memory (they start over when the app restarts). STATUS_SAMPLE_SECONDS > 0 starts a thread that
# probes on its own, so the history fills without visitors; pages probe at most every 5 seconds.
SERVICES = [
    ("product-catalog-service", lambda: f"http://{product_catalog}:{product_port}"),
    ("user-management-service", lambda: f"http://{user_management}:{user_port}"),
    ("order-processing-service", lambda: f"http://{order_processing}:{order_port}"),
]
_status_history = {name: deque(maxlen=120) for name, _ in SERVICES}
_status_lock = threading.Lock()
_last_probe = [0.0]


def probe_services(force: bool = False) -> None:
    with _status_lock:
        if not force and time.time() - _last_probe[0] < 5:
            return
        _last_probe[0] = time.time()
    for name, url in SERVICES:
        started = time.perf_counter()
        try:
            response = requests.get(url(), timeout=3)
            text = response.text.strip().strip('"')
            up = response.status_code == 200
        except requests.exceptions.RequestException:
            text, up = "Failed to fetch data", False
        ms = round((time.perf_counter() - started) * 1000, 1)
        with _status_lock:
            _status_history[name].append({"at": time.time(), "up": up, "ms": ms, "text": text})


def status_summary() -> list:
    with _status_lock:
        history = {name: list(samples) for name, samples in _status_history.items()}
    summary = []
    for name, _ in SERVICES:
        samples = history[name]
        last = samples[-1] if samples else {"up": False, "ms": None, "text": "Not checked yet"}
        up_count = sum(1 for s in samples if s["up"])
        summary.append({
            "name": name,
            # "status" keeps the classic template's check (== "Success") working
            "status": "Success" if last["up"] else last["text"],
            "up": last["up"],
            "ms": last["ms"],
            "uptime": round(100 * up_count / len(samples), 1) if samples else None,
            "samples": len(samples),
            "series": [s["ms"] if s["up"] else None for s in samples[-60:]],
        })
    return summary


def sparkline(series: list, width: int = 240, height: int = 44) -> str:
    """SVG points for the response times (None = down, a gap); scaled to the largest value."""
    values = [v for v in series if v is not None]
    if len(series) < 2 or not values:
        return ""
    top = max(values) or 1
    step = width / (len(series) - 1)
    return " ".join(
        f"{i * step:.1f},{height - 2 - (v / top) * (height - 4):.1f}"
        for i, v in enumerate(series) if v is not None
    )


def _sampler(every: float) -> None:
    while True:
        try:
            probe_services(force=True)
        except Exception:
            pass
        time.sleep(every)


STATUS_SAMPLE_SECONDS = float(os.environ.get("STATUS_SAMPLE_SECONDS", "0") or 0)
if STATUS_SAMPLE_SECONDS > 0:
    threading.Thread(target=_sampler, args=(STATUS_SAMPLE_SECONDS,), daemon=True).start()


@app.route("/server/")
def server() -> tuple:
    probe_services()
    status = status_summary()
    for service in status:
        service["points"] = sparkline(service["series"])
    return render(
        "server.html",
        utc_dt=datetime.datetime.utcnow(),
        status=status,
        user=check_user_auth(),
        value=get_count_for_current_user(),
    )


@app.route("/status.json")
def status_json() -> tuple:
    probe_services()
    status = status_summary()
    for service in status:
        service["points"] = sparkline(service["series"])
        del service["series"]
    return jsonify({"checked": datetime.datetime.utcnow().strftime("%H:%M:%S"), "services": status})


@app.route("/status/checks.json")
def status_checks() -> tuple:
    """Deeper checks than "does it answer": each one does what a page would need, timed."""
    def timed(name, check):
        started = time.perf_counter()
        try:
            ok, detail = check()
        except Exception as e:
            ok, detail = False, type(e).__name__
        return {"name": name, "ok": ok, "detail": detail, "ms": round((time.perf_counter() - started) * 1000, 1)}

    def products():
        found = requests.get(f"http://{product_catalog}:{product_port}/api/products/1", timeout=5).json()
        return isinstance(found, list) and len(found) > 0, f"{len(found)} products on page 1"

    def accounts():
        response = requests.get(f"http://{user_management}:{user_port}", timeout=5)
        return response.status_code == 200, f"HTTP {response.status_code}"

    def orders():
        response = requests.get(f"http://{order_processing}:{order_port}", timeout=5)
        return response.status_code == 200, f"HTTP {response.status_code}"

    def rates():
        date = exchange_rates()["date"]
        if not date:
            return False, "no ECB rates yet (fallback rates in use)"
        age = (datetime.date.today() - datetime.date.fromisoformat(date)).days
        return age <= 4, f"ECB rates of {date}"

    checks = [
        timed("Products load", products),
        timed("Accounts answer", accounts),
        timed("Orders answer", orders),
        timed("Exchange rates are fresh", rates),
    ]
    return jsonify({"ok": all(c["ok"] for c in checks), "checks": checks})


# ---------- The admin's dashboard ----------
def sales_summary(orders: list, days: int = 14) -> dict:
    """What the dashboard shows, from every order: totals, orders and revenue per day for the last
    `days` days, orders per currency, the best sellers and how many kept the pre-ticked add-on."""
    orders = [o for o in orders if isinstance(o, dict)]
    today = datetime.date.today()
    per_day = {(today - datetime.timedelta(days=n)).isoformat(): {"orders": 0, "revenue": Decimal("0")}
               for n in range(days - 1, -1, -1)}
    revenue = Decimal("0")
    currencies, sellers = Counter(), Counter()
    with_addon = 0
    for order in orders:
        amount = euro_amount(order.get("price")) or Decimal("0")
        revenue += amount
        day = str(order.get("time", ""))[:10]
        if day in per_day:
            per_day[day]["orders"] += 1
            per_day[day]["revenue"] += amount
        currencies[order.get("currency", "EUR")] += 1
        for item in order.get("history") or []:
            if isinstance(item, dict) and item.get("order"):
                sellers[item["order"]] += 1
        if order.get("extras"):
            with_addon += 1
    count = len(orders)
    return {
        "orders": count,
        "revenue": revenue,
        "average": (revenue / count).quantize(Decimal("0.01")) if count else Decimal("0"),
        "addon_rate": round(100 * with_addon / count) if count else 0,
        "with_addon": with_addon,
        "per_day": [{"day": day, **values} for day, values in per_day.items()],
        "currencies": currencies.most_common(),
        "sellers": sellers.most_common(5),
    }


def bar_chart(per_day: list, width: int = 640, height: int = 180) -> dict:
    """Bars for orders per day, as SVG geometry: one series, one axis, a label every few days."""
    top = max([d["orders"] for d in per_day] + [1])
    slot = width / len(per_day)
    bar = max(slot - 6, 4)
    bars = []
    for i, d in enumerate(per_day):
        # 18 px at the bottom for the day labels, 16 at the top for the tallest bar's number
        h = (d["orders"] / top) * (height - 18 - 16)
        bars.append({
            "x": round(i * slot + (slot - bar) / 2, 1), "y": round(height - 18 - h, 1),
            "w": round(bar, 1), "h": round(h, 1), "day": d["day"], "orders": d["orders"],
            "revenue": d["revenue"], "label": d["day"][5:] if i % 3 == 0 or i == len(per_day) - 1 else "",
        })
    return {"width": width, "height": height, "top": top, "bars": bars}


@app.route("/admin/")
@admin_route
def admin_dashboard() -> tuple:
    try:
        orders = requests.get(f"http://{order_processing}:{order_port}/api/orders", timeout=5).json()
    except (requests.exceptions.RequestException, ValueError):
        orders = []
    summary = sales_summary(orders if isinstance(orders, list) else [])
    try:
        users = requests.get(f"http://{user_management}:{user_port}/api/users", timeout=5).json()
        user_count = len(users) if isinstance(users, list) else None
    except (requests.exceptions.RequestException, ValueError):
        user_count = None
    return render(
        "admin.html",
        summary=summary,
        chart=bar_chart(summary["per_day"]),
        user_count=user_count,
        message=request.args.get("message", ""),
        user=check_user_auth(),
        value=get_count_for_current_user(),
    )


@app.route("/admin/users", methods=["POST"])
@admin_route
def admin_create_user() -> tuple:
    """The admin makes a customer account (user-management-service makes every account one)."""
    fields = {key: request.form.get(key, "").strip() for key in ("username", "name", "email", "password")}
    if not all(fields.values()):
        return redirect(url_for("admin_dashboard", message="All four fields are needed."))
    avatar = request.form.get("avatar")
    fields["avatar"] = avatar if avatar in AVATARS else AVATARS[0]
    try:
        response = requests.post(f"http://{user_management}:{user_port}/api/user", json=fields, timeout=5)
    except requests.exceptions.RequestException:
        return redirect(url_for("admin_dashboard", message="The account service did not answer."))
    if response.status_code == 201:
        return redirect(url_for("admin_dashboard", message=f"Account {fields['username']} created."))
    try:
        reason = response.json().get("message", "")
    except (ValueError, AttributeError):
        reason = ""
    return redirect(url_for("admin_dashboard", message=f"Not created. {reason}".strip()))


# Very important to disable debug mode
app.run(host="0.0.0.0", port=server_port, debug=False, use_reloader=False)
