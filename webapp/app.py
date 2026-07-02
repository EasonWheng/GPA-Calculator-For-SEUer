"""GPA Calculator for SEUer — Flask Web App"""
import sys
import os
import threading
import webbrowser
from flask import Flask, request, jsonify, render_template

# Ensure we can import gpa_engine from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gpa_engine import calculate_all, get_defaults

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/defaults")
def api_defaults():
    return jsonify(get_defaults())


@app.route("/api/calculate", methods=["POST"])
def api_calculate():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": True, "message": "请求体为空或格式错误。请粘贴有效的 JSON。"}), 400

    json_text = data.get("json_data", "").strip()
    if not json_text:
        return jsonify({"error": True, "message": "未提供成绩 JSON 数据。"}), 400

    keywords = data.get("keywords", [])
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.replace("，", ",").split(",") if k.strip()]

    excludes = data.get("excludes", [])
    if isinstance(excludes, str):
        excludes = [e.strip() for e in excludes.replace("，", ",").split(",") if e.strip()]

    gpa_type = data.get("gpa_type", "4.8")
    if gpa_type not in ("4.0", "4.8"):
        gpa_type = "4.8"

    result = calculate_all(json_text, keywords, excludes, gpa_type)
    return jsonify(result)


def open_browser():
    webbrowser.open_new("http://127.0.0.1:59876")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="GPA Calculator for SEUer")
    parser.add_argument("--port", type=int, default=59876, help="Server port")
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open browser")
    args = parser.parse_args()

    if not args.no_browser:
        threading.Timer(1.0, open_browser).start()

    print(f"\n  GPA Calculator for SEUer 已启动")
    print(f"  浏览器访问: http://127.0.0.1:{args.port}\n")
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
