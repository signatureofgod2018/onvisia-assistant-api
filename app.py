import os
import re
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

# Matches agent citation markers such as 【4:0†Some Document.pdf】
CITATION_PATTERN = re.compile(r"\s*【[^】]*】")

# Conversation history limits (keeps cost and abuse in check).
MAX_HISTORY_TURNS = 20
MAX_CONTENT_CHARS = 4000
ALLOWED_ROLES = {"user", "assistant"}


def build_input(message, history):
    """Build the agent input from prior turns plus the current message.

    Only user/assistant turns are accepted, so callers cannot inject
    system or developer instructions.
    """
    turns = []
    if isinstance(history, list):
        for item in history:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            content = item.get("content")
            if role in ALLOWED_ROLES and isinstance(content, str) and content.strip():
                turns.append({"role": role, "content": content[:MAX_CONTENT_CHARS]})

    message = message.strip()[:MAX_CONTENT_CHARS] if isinstance(message, str) else ""

    # The UI may already include the current message as the last history turn.
    if message and not (turns and turns[-1] == {"role": "user", "content": message}):
        turns.append({"role": "user", "content": message})

    return turns[-MAX_HISTORY_TURNS:]


@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "Onvisia Assistant API",
        "agent": AGENT_NAME,
        "version": AGENT_VERSION
    })


@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(force=True, silent=True)
        if not isinstance(data, dict):
            data = {}

        turns = build_input(data.get("message", ""), data.get("messages"))

        if not turns or turns[-1]["role"] != "user":
            return jsonify({
                "reply": "Please enter a question."
            }), 400

        response = openai_client.responses.create(
            input=turns,
            extra_body={
                "agent_reference": {
                    "name": AGENT_NAME,
                    "version": AGENT_VERSION,
                    "type": "agent_reference"
                }
            }
        )

        # Strip citation markers so internal document names are not exposed.
        reply = CITATION_PATTERN.sub("", response.output_text).strip()

        return jsonify({
            "reply": reply
        })

    except Exception:
        # Log full details server-side (visible in App Service Log stream);
        # never return internal error text to callers.
        app.logger.exception("Chat request failed")
        return jsonify({
            "reply": "Assistant error."
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
