from flask import Flask, render_template, redirect, url_for, request, jsonify
import datetime
import json
import requests
import stripe
import os
from prometheus_flask_exporter import PrometheusMetrics
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user


stripe.api_key = 'sk_test_51OexmCIffcetN3aYn6rn9dlZIhjDwLgbz0Xw0P0WCV1YXVaMUbT1WET9GkkXkprTwdfqgSgLa0M9C8j5vtflPcjs00F9Bp9d64'

# Initialize Flask-Login
login_manager = LoginManager()

app = Flask(__name__,
            static_url_path='',
            static_folder='public')

YOUR_DOMAIN = 'http://localhost:4004'
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



@app.route("/update/", methods=["POST"])
def update_p():
    # return request.form['id']
    id =  request.form['id']
    order = request.form['updateOrder']
    price = request.form['updatePrice']
    
    json_data = json.dumps({
        'order': order,
        'price': price
    })
    d_url = 'http://scamazon-product-catalog-service-1:4005/api/product/{}'.format(id)
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
    add_url = 'http://scamazon-product-catalog-service-1:4005/api/product'
     
    json_data = json.dumps({
        'order': order,
        'price': price
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

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
                    'price': 'price_1OeyzyIffcetN3aY2LhK5buH',
                    'quantity': 1,
                },
            ],
            mode='payment',
            success_url=YOUR_DOMAIN + '/success',
            cancel_url=YOUR_DOMAIN + '/cancel',
        )
    except Exception as e:
        return str(e)

    return redirect(checkout_session.url, code=303)

@app.route('/session-status', methods=['GET'])
def session_status():
  session = stripe.checkout.Session.retrieve(request.args.get('session_id'))

  return jsonify(status=session.status, customer_email=session.customer_details.email)

@app.route("/checkout")
def checkout():
    return render_template("checkout.html")

@app.route("/cancel")
def cancel():
    return render_template("cancel.html")

@app.route("/success")
def success():
    return render_template("success.html")
 


# Very important to disable debug mode
if __name__ == '__main__':
    app.run(port=4004, debug=True)
