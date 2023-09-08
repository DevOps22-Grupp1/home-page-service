from flask import Flask
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
def hello_world():
    r1 = requests.get("http://order-processing-service:5001")
    r2 = requests.get("http://produkt-catalog-service:5004")
    return f"Hello from home-page-service. order-processing-service says: {r1.text}! - user-managament-service says {r2.text}"


# Very important to disable debug mode
app.run(host="0.0.0.0", port=5002, debug=False)
