from flask import Flask, render_template, redirect, url_for, request, jsonify, abort
import datetime
import json
import os
from functools import wraps
import requests
from werkzeug.middleware.proxy_fix import ProxyFix
from prometheus_flask_exporter import PrometheusMetrics
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user



# Initialize Flask-Login
login_manager = LoginManager()

app = Flask(__name__)
# Behind a proxy on a sub-path (e.g. Traefik on /scamazon): X-Forwarded-Prefix makes url_for()
# build links with the prefix. Without a proxy it changes nothing.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key')  # Set SECRET_KEY in production

# READ_ONLY=1: a public demo where nobody can log in or change the products
READ_ONLY = os.environ.get('READ_ONLY') == '1'

# The other services; the defaults are the container names in the compose project "scamazon"
PRODUCT_SERVICE = os.environ.get('PRODUCT_SERVICE_URL', 'http://scamazon-product-catalog-service-1:4005')
USER_SERVICE = os.environ.get('USER_SERVICE_URL', 'http://scamazon-user-management-service-1:4006')
ORDER_SERVICE = os.environ.get('ORDER_SERVICE_URL', 'http://scamazon-order-processing-service-1:4007')
# Seconds a call to another service may take before the page gives up
TIMEOUT = 5

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
users = {os.environ.get('ADMIN_USER', 'user1'): {'password': os.environ.get('ADMIN_PASSWORD', 'password1')}}


def admin_route(view):
    """Admin pages: require login, and do not exist at all in read-only mode."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if READ_ONLY:
            abort(403)
        return login_required(view)(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_read_only():
    return {'read_only': READ_ONLY}


@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

@metrics.counter(
    "invocation_by_method",
    "Number of invocations by HTTP method",
)
@app.route("/")
def hello():
    return render_template("index.html", utc_dt=datetime.datetime.utcnow())


@app.route('/admin-product/')
@admin_route
def handle_products():

    response = requests.get(PRODUCT_SERVICE + '/api/products', timeout=TIMEOUT)

    if response.status_code == 200:
        products = json.loads(response.text)
        return render_template("admin-product-html", products=products)
    else:
        return jsonify({'error': 'Failed to fetch data'})


@app.route("/login/", methods=["GET"])
def get_login():
    if READ_ONLY:
        abort(403)
    return render_template('login.html')


@app.route("/delete/", methods=["GET"])
@admin_route
def delete_p():
    id = request.args.get('id')
    delete_url = PRODUCT_SERVICE + '/api/product/{}'.format(id)
    response = requests.delete(delete_url, timeout=TIMEOUT)
    if response.status_code == 204:
        # The DELETE request was successful, and there's no response content.
        return redirect(url_for('handle_products'))
    elif response.status_code == 404:
        return jsonify({'error': 'Product not found'})
    else:
        return jsonify({'error': 'Failed to delete product'})



@app.route("/update/", methods=["POST"])
@admin_route
def update_p():
    # return request.form['id']
    id =  request.form['id']
    order = request.form['updateOrder']
    price = request.form['updatePrice']
    
    json_data = json.dumps({
        'order': order,
        'price': price
    })
    d_url = PRODUCT_SERVICE + '/api/product/{}'.format(id)
    headers = {'Content-Type': 'application/json'}
    response = requests.put(d_url, data=json_data, headers=headers, timeout=TIMEOUT)
    if response.status_code == 200:
        # The POST request was successful
        return redirect(url_for('handle_products'))
    else:
        return f"POST request returned a status code: {response.status_code}"
        # You can handle different status codes as needed


@app.route("/add_products/", methods=["POST"])
@admin_route
def post_product():
    order = request.form['name']
    price = request.form['price']
    add_url = PRODUCT_SERVICE + '/api/product'
     
    json_data = json.dumps({
        'order': order,
        'price': price
    })
    headers = {'Content-Type': 'application/json'}
    response = requests.post(add_url, data=json_data, headers=headers, timeout=TIMEOUT)
    if response.status_code == 201:
        # The POST request was successful
        return redirect(url_for('handle_products'))
    else:
        return f"POST request returned a status code: {response.status_code}"
        # You can handle different status codes as needed
    

@app.route("/login/", methods=["POST"])
def post_login():
    if READ_ONLY:
        abort(403)
    username = request.form['username']
    password = request.form['password']
    
    if username in users and users[username]['password'] == password:
        user = User(username)
        login_user(user)
        return redirect(url_for('handle_products'))
    return redirect(url_for('get_login'))

@app.route("/about/")
def about():
    return render_template("about.html")

@app.route("/products/")
def products():
    try:
        products = 'Failed to fetch data'
        response = requests.get(PRODUCT_SERVICE + '/api/products', timeout=TIMEOUT)
        if response.status_code == 200:
            products = json.loads(response.text)
    except requests.exceptions.RequestException as e:
        products = 'Failed to fetch data'
  
    return render_template("products.html", products=products)


    ### Make requests to the other services and return the result ok or not ok ###
@app.route("/server/")
def server():
    try:
        r1 = 'Failed to fetch data'
        res1 = requests.get(PRODUCT_SERVICE, timeout=TIMEOUT)
        if res1.status_code == 200:
            r1 = res1.text
    except requests.exceptions.RequestException as e:
        r1 = 'Failed to fetch data'
    
    
    try:
        r2 = 'Failed to fetch data'
        res2 = requests.get(USER_SERVICE, timeout=TIMEOUT)
        if res2.status_code == 200:
            r2 = res2.text
    except requests.exceptions.RequestException as e:
        r2 = 'Failed to fetch data'
    
    
    try:
        r3 = 'Failed to fetch data'
        res3 = requests.get(ORDER_SERVICE, timeout=TIMEOUT)
        if res3.status_code == 200:
            r3 = res3.text
    except requests.exceptions.RequestException as e:
        r3 = 'Failed to fetch data'
    

    
    status = [{"name": "product-catalog-service", "status": r1}, {"name": "user-managament-service", "status": r2}, {"name": "order-processing-service", "status": r3}]


    return render_template("server.html", utc_dt=datetime.datetime.utcnow(), status=status)

 


# Very important to disable debug mode: the Werkzeug debugger lets anyone run code.
# FLASK_DEBUG=1 turns it on locally.
app.run(host="0.0.0.0", port=4004, debug=os.environ.get('FLASK_DEBUG') == '1')
