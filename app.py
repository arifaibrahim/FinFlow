from flask import Flask, render_template, jsonify

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/test")
def api_test():
    return jsonify({
        "message": "FinFlow backend connected",
        "status": "success"
    })


if __name__ == "__main__":
    app.run(debug=True)