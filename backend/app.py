from flask import Flask, render_template, redirect, url_for, request, jsonify
import datetime
import json
import requests
from prometheus_flask_exporter import PrometheusMetrics
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os
server_port = os.environ.get("DB_PORT")
user_management = os.environ.get("USER_URL")
user_port = int(os.environ.get("USER_PORT"))
product_catalog = os.environ.get("PRODUCT_URL")
product_port = int(os.environ.get("PRODUCT_PORT"))
order_processing= os.environ.get("ORDER_URL")
order_port = int(os.environ.get("ORDER_PORT"))

# Initialize Flask-Login
login_manager = LoginManager()

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure secret key

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
users = {'user1': {'password': 'password1'}}


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
@login_required
def handle_products():
    try:
        response = requests.get(
            f'http://{product_catalog}:{product_port}/api/products')
        if response.status_code == 200:
            products = json.loads(response.text)
    except requests.exceptions.RequestException as e:
        products = 'Failed to fetch data'
  
    return render_template("admin-product.html", products=products)


@app.route("/login/", methods=["GET"])
def get_login():
    return render_template('login.html')


@app.route("/delete/", methods=["GET"])
def delete_p():
    id = request.args.get('id')
    delete_url = f'http://{product_catalog}:{product_port}/api/product/{id}'
    response = requests.delete(delete_url)
    if response.status_code == 204:
        # The DELETE request was successful, and there's no response content.
        return redirect(url_for('handle_products'))
    elif response.status_code == 404:
        return jsonify({'error': 'Product not found'})
    else:
        return jsonify({'error': 'Failed to delete product'})



@app.route("/update/", methods=["POST"])
def update_p():
    # return request.form['id']
    id =  request.form['id']
    order = request.form['updateOrder']
    price = request.form['updatePrice']
    img = request.form["updateImg"]
    
    json_data = json.dumps({
        'order': order,
        'price': price, 
        "image": img
    })
    d_url = f'http://{product_catalog}:{product_port}/api/product/{id}'
    headers = {'Content-Type': 'application/json'}
    response = requests.put(d_url, data=json_data, headers=headers)
    if response.status_code == 200:
        # The POST request was successful
        return redirect(url_for('handle_products'))
    else:
        return f"POST request returned a status code: {response.status_code}"
        # You can handle different status codes as needed


@app.route("/add_products/", methods=["POST"])
def post_product():
    order = request.form['name']
    price = request.form['price']
    img = request.form["images"]
    add_url = f'http://{product_catalog}:{product_port}/api/product'
     
    json_data = json.dumps({
        'order': order,
        'price': price,
         "image": img
    })
    headers = {'Content-Type': 'application/json'}
    response = requests.post(add_url, data=json_data, headers=headers)
    if response.status_code == 201:
        # The POST request was successful
        return redirect(url_for('handle_products'))
    else:
        return f"POST request returned a status code: {response.status_code}"
        # You can handle different status codes as needed
    

@app.route("/login/", methods=["POST"])
def post_login():
    username = request.form['username']
    password = request.form['password']
    
    if username in users and users[username]['password'] == password:
        user = User(username)
        login_user(user)
        return redirect(url_for('handle_products'))

@app.route("/about/")
def about():
    return render_template("about.html")

@app.route("/products/")
def products():
    try:
        response = requests.get(
            f'http://{product_catalog}:{product_port}/api/products')
        if response.status_code == 200:
            products = json.loads(response.text)
    except requests.exceptions.RequestException as e:
        products = 'Failed to fetch data'
  
    return render_template("products.html", products=products)

    # AT THIS MOMENT NOT WORKING - RESEARCH HOW TO GET THE DATA FROM THE OTHER SERVICE #
    products = requests.get('http://scamazon-product-catalog-service-1:4005/api/products').json()
    products = products.sringify()
    

    return render_template("products.html", products=products, utc_dt=datetime.datetime.utcnow())

    ### Make requests to the other services and return the result ok or not ok ###
@app.route("/server/")
def server():
    try:
        res1 = requests.get(f"http://{product_catalog}:{product_port}")
        if res1.status_code == 200:
            r1 = res1.text
    except requests.exceptions.RequestException as e:
        r1 = 'Failed to fetch data'
    
    
    try:
        res2 = requests.get(f"http://{user_management}:{user_port}")
        if res2.status_code == 200:
            r2 = res2.text
    except requests.exceptions.RequestException as e:
        r2 = 'Failed to fetch data'
    
    
    try:
        res3 = requests.get(f"http://{order_processing}:{order_port}")
        if res3.status_code == 200:
            r3 = res3.text
    except requests.exceptions.RequestException as e:
        r3 = 'Failed to fetch data'
    

    
    status = [{"name": "product-catalog-service", "status": r1}, {"name": "user-managament-service", "status": r2}, {"name": "order-processing-service", "status": r3}]


    return render_template("server.html", utc_dt=datetime.datetime.utcnow(), status=status)

 
# Very important to disable debug mode
app.run(host="0.0.0.0", port=server_port, debug=False)
