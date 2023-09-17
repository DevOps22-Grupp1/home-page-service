from flask import Flask, render_template, redirect, url_for, request, jsonify
import datetime
import json
import requests
from prometheus_flask_exporter import PrometheusMetrics
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user



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

    response = requests.get(
        'http://scamazon-product-catalog-service-1:4005/api/products')

    if response.status_code == 200:
        products = json.loads(response.text)
        return render_template("admin-product-html", products=products)
    else:
        return jsonify({'error': 'Failed to fetch data'})


@app.route("/login/", methods=["GET"])
def get_login():
    return render_template('login.html')


@app.route("/delete/", methods=["GET"])
def delete_p():
    id = request.args.get('id')
    delete_url = 'http://scamazon-product-catalog-service-1:4005/api/product/{}'.format(id)
    response = requests.delete(delete_url)
    if response.status_code == 204:
        # The DELETE request was successful, and there's no response content.
        return redirect(url_for('handle_products'))
    elif response.status_code == 404:
        return jsonify({'error': 'Product not found'})
    else:
        return jsonify({'error': 'Failed to delete product'})



@app.route("/update/", methods=["GET"])
def update_p():
    id = request.args.get('id')
    order = request.args.get("name")
    # delete_url = 'http://scamazon-product-catalog-service-1:4005/api/product/{}'.format(id)
    # response = requests.delete(delete_url)
    # if response.status_code == 204:
    #     # The DELETE request was successful, and there's no response content.
    #     return redirect(url_for('handle_products'))
    # elif response.status_code == 404:
    #     return jsonify({'error': 'Product not found'})
    # else:
    #     return jsonify({'error': 'Failed to delete product'})
    return f"{order}"

    # <a href="{{ url_for('update_p', id= product.id, name=product.order ) }}">Update</a>

    # if response.status_code == 200:
    #     products = json.loads(response.text)
    #     # return render_template("admin-product-html", products=products)
    #     return f"{products}"
    # else:
    #     return jsonify({'error': 'Failed to fetch data'})


@app.route("/add_products/", methods=["POST"])
def post_product():
    order = request.form['name']
    price = request.form['price']
    add_url = 'http://scamazon-product-catalog-service-1:4005/api/product'
    
    data = {
        'order': order,
        'price': price
    }
    json_data = json.dumps(data)
    headers = {'Content-Type': 'application/json'}
    response = requests.post(add_url, data=json_data, headers=headers)
    if response.status_code == 201:
        # The POST request was successful
        return redirect(url_for('handle_products'))
    else:
        return f"POST request returned a status code: {response.status_code}"
        # You can handle different status codes as needed

    
    return f"{order} {price}" 
    

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
    response = requests.get('http://scamazon-product-catalog-service-1:4005/api/products') 

    if response.status_code == 200:
        products = json.loads(response.text)
        return render_template("products.html", products=products)
    else:
        return jsonify({'error': 'Failed to fetch data'})
  
    
#  images=images, prices=prices

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
    # r2 = requests.get("http://scamazon-product-catalog-service-1:4005/")
    # return f"order-processing-service says: {r1.text}! - user-managament-service says {r2.text} - product-catalog-service says {r3.text}" 


# Very important to disable debug mode
app.run(host="0.0.0.0", port=5002, debug=True)
