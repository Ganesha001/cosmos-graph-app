import os
import time
import logging
import traceback
from flask import Flask, render_template, request, jsonify
from gremlin_python.driver.client import Client
from gremlin_python.structure.graph import Graph
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection

app = Flask(__name__)

# Retrieve environment variables for Azure Cosmos DB
COSMOS_DB_ENDPOINT = os.getenv("COSMOS_DB_ENDPOINT")
COSMOS_DB_KEY = os.getenv("COSMOS_DB_KEY")
GRAPH_DB_NAME = os.getenv("GRAPH_DB_NAME")

# Create a single Gremlin client object outside any function
client = Client(
    f"{COSMOS_DB_ENDPOINT}gremlin",
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
        client.submit("g.V().limit(1)")
        return jsonify({"status": "success", "message": "Connection to Cosmos DB Gremlin API successful!"})
    except Exception as e:
        app.logger.error(f"Error testing connection: {str(e)}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": "An error occurred while testing the connection. Please check your Cosmos DB credentials and network connectivity."})

@app.route("/add_vertex", methods=["POST"])
def retry_with_exponential_backoff(func, max_retries=5, initial_backoff=1, max_backoff=60):
    """
    Retries a function with exponential backoff.

    Args:
        func: The function to retry.
        max_retries: Maximum number of retries.
        initial_backoff: Initial backoff time in seconds.
        max_backoff: Maximum backoff time in seconds.

    Returns:
        The result of the function call or raises the last exception.
    """
    retries = 0
    backoff = initial_backoff
    while retries < max_retries:
        try:
            return func()
        except RuntimeError as e:
            if "Connection was closed by server" in str(e):
                app.logger.warning(f"Attempt {retries}/{max_retries}: Connection closed by server. Retrying...")
                # Reconnect to Cosmos DB
                global client  # Access the global client variable
                client.close()  # Close the existing connection
                client = Client(
                    f"{COSMOS_DB_ENDPOINT}gremlin",
                    "g",
                    username=f"/dbs/{GRAPH_DB_NAME}/colls/RelationshipGraph",
                    password=COSMOS_DB_KEY,
                    connection=DriverRemoteConnection(url=f"{COSMOS_DB_ENDPOINT}gremlin", keepAlive=True),
                )
                retries += 1
                if retries == max_retries:
                    raise
                time.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
            else:
                raise  # Re-raise other exceptions

    raise Exception("Failed to add vertex after retries")

@app.route("/add_vertex", methods=["POST"])
def add_vertex():
    try:
        data = request.json
        label = data.get("label")
        properties = data.get("properties", {})

        query = f"g.addV('{label}')"
        for key, value in properties.items():
            query += f".property('{key}', '{value}')"

        result = retry_with_exponential_backoff(lambda: client.submit(query).all().result())
        return jsonify({"status": "success", "message": "Vertex added successfully", "result": str(result)})
    except Exception as e:
        app.logger.error(f"Error adding vertex: {str(e)}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": "An error occurred while adding the vertex. Please try again later."})
        
@app.route("/add_edge", methods=["POST"])
def add_edge():
    try:
        data = request.json
        from_vertex = data.get("from_vertex")
        to_vertex = data.get("to_vertex")
        edge_label = data.get("edge_label")
        properties = data.get("properties", {})

        query = f"g.V().has('id', '{from_vertex}').addE('{edge_label}').to(g.V().has('id', '{to_vertex}'))"
        for key, value in properties.items():
            query += f".property('{key}', '{value}')"

        result = client.submit(query).all().result()
        return jsonify({"status": "success", "message": "Edge added successfully", "result": str(result)})
    except Exception as e:
        app.logger.error(f"Error adding edge: {str(e)}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": "An error occurred while adding the edge. Please check the vertex IDs and edge label."})

@app.route("/get_vertices", methods=["GET"])
def get_vertices():
    try:
        result = client.submit("g.V()").all().result()
        return jsonify({"status": "success", "vertices": result})
    except Exception as e:
        app.logger.error(f"Error getting vertices: {str(e)}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": "An error occurred while retrieving vertices. Please try again later."})

@app.route("/get_edges", methods=["GET"])
def get_edges():
    try:
        result = client.submit("g.E()").all().result()
        return jsonify({"status": "success", "edges": result})
    except Exception as e:
        app.logger.error(f"Error getting edges: {str(e)}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": "An error occurred while retrieving edges. Please try again later."})

if __name__ == '__main__':
    # Configure logging to a file or to the console
    app.logger.setLevel(logging.DEBUG)  # Adjust the log level as needed
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler = logging.FileHandler('app.log')  # Or use logging.StreamHandler() for console
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)

    app.run(host='0.0.0.0', port=8080, debug=True)
