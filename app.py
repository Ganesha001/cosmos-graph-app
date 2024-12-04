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
    password=COSMOS_DB_KEY,
    message_serializer=None,
    pool_size=10,
    max_workers=10,
    # traversal_source="g",
    max_content_length=2097152,
    # max_retries=3,
    timeout=600  # Increase timeout to 60 seconds
)

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
                )
                retries += 1
                if retries == max_retries:
                    raise
                time.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
            else:
                raise  # Re-raise other exceptions
    raise Exception("Failed to execute function after retries")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/add_vertex", methods=["POST"])
def add_vertex():
    try:
        data = request.json
        label = data.get("label")
        properties = data.get("properties", {})

        # Construct the Gremlin query
        query = f"g.addV('{label}')"
        for key, value in properties.items():
            query += f".property('{key}', '{value}')"

        # Call the retry_with_exponential_backoff function with the query
        result = retry_with_exponential_backoff(lambda: client.submit(query).all().result())
        
        return jsonify({"status": "success", "message": "Vertex added successfully", "result": str(result)})
    except Exception as e:
        app.logger.error(f"Error adding vertex: {str(e)}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": "An error occurred while adding the vertex. Please try again later."})


if __name__ == '__main__':
    # Configure logging to a file or to the console
    app.logger.setLevel(logging.DEBUG)  # Adjust the log level as needed
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler = logging.FileHandler('app.log')  # Or use logging.StreamHandler() for console
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)

    app.run(host='0.0.0.0', port=8080, debug=True)