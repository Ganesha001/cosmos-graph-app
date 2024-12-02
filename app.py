import os
from flask import Flask, render_template, request, jsonify
from gremlin_python.driver.client import Client

app = Flask(__name__)

# Retrieve environment variables for Azure Cosmos DB
COSMOS_DB_ENDPOINT = os.getenv("COSMOS_DB_ENDPOINT")
COSMOS_DB_KEY = os.getenv("COSMOS_DB_KEY")
GRAPH_DB_NAME = os.getenv("GRAPH_DB_NAME")

# Initialize Gremlin client
def get_gremlin_client():
    return Client(
        f"{COSMOS_DB_ENDPOINT}/gremlin", 
        "g", 
        username=f"/dbs/{GRAPH_DB_NAME}/colls/RelationshipGraph",
        password=COSMOS_DB_KEY
    )

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/test_connection", methods=["POST"])
def test_connection():
    try:
        client = get_gremlin_client()
        client.submit("g.V().limit(1)")
        return jsonify({"status": "success", "message": "Connection to Cosmos DB Gremlin API successful!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
