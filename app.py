# from flask import Flask, request, jsonify
# from infer import infer

# app = Flask(__name__)


# @app.route("/infer", methods=["POST"])
# def handle_infer():
#     prompt = request.json.get("prompt", "")
#     response = infer(prompt)
#     return jsonify({"response": response})


# if __name__ == "__main__":
#     app.run(debug=True, host="0.0.0.0", port=5000)
