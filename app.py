import os
from flask import Flask, request, jsonify
from flask_cors import CORS
 
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
 
app = Flask(__name__)
 
CORS(
app,
resources={
r"/*": {
"origins": [
"https://www.onvisia.ai",
"http://127.0.0.1:8765"
]
}
}
)
 
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
 
project_client = AIProjectClient(
endpoint=PROJECT_ENDPOINT,
credential=DefaultAzureCredential()
)
 
openai_client = project_client.get_openai_client()
 
AGENT_NAME = "Onvisia-Knowledge-Assistant"
AGENT_VERSION = "6"
 
 
@app.route("/", methods=["GET"])
def health():
return jsonify({
"status": "ok",
"service": "Onvisia Assistant API"
})
 
 
@app.route("/chat", methods=["POST"])
def chat():
try:
data = request.get_json(force=True)
 
message = data.get("message", "")
 
response = openai_client.responses.create(
input=[
{
"role": "user",
"content": message
}
],
extra_body={
"agent_reference": {
"name": AGENT_NAME,
"version": AGENT_VERSION,
"type": "agent_reference"
}
}
)
 
return jsonify({
"reply": response.output_text
})
 
except Exception as ex:
return jsonify({
"reply": "Assistant error.",
"error": str(ex)
}), 500
 
 
if __name__ == "__main__":
app.run(host="0.0.0.0", port=8000)
