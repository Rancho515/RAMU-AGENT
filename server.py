from flask import Flask, request, jsonify, render_template
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import subprocess

app = Flask(__name__)

scheduler = BackgroundScheduler()
scheduler.start()

calls = []


def run_call(call):
    try:
        call["status"] = "calling"

        result = subprocess.run(
            ["python", "make_call.py", "--to", call["phone"]],
            capture_output=True,
            text=True
        )

        output = (result.stdout or "") + (result.stderr or "")

        if "Call answered" in output:
            call["status"] = "answered"
            call["message"] = "Call picked up"

        elif "sip status: 480" in output:
            call["status"] = "not_picked"
            call["message"] = "Call initiated but not picked up"

        elif "sip status: 403" in output:
            call["status"] = "rejected"
            call["message"] = "Call rejected / blocked"

        elif "sip status: 404" in output or "sip status: 484" in output:
            call["status"] = "invalid"
            call["message"] = "Incorrect phone number"

        elif result.returncode == 0:
            call["status"] = "completed"
            call["message"] = "Call finished normally"

        else:
            call["status"] = "error"
            call["message"] = "Unknown call error"

    except Exception as e:
        call["status"] = "error"
        call["message"] = str(e)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/schedule_call", methods=["POST"])
def schedule_call():
    data = request.json

    phone = data["phone"]
    time = data["time"]

    run_time = datetime.strptime(time, "%Y-%m-%dT%H:%M")

    call = {
        "phone": phone,
        "time": time,
        "status": "pending",
        "message": ""
    }

    calls.append(call)

    scheduler.add_job(
        run_call,
        "date",
        run_date=run_time,
        args=[call]
    )

    return jsonify({"status": "scheduled"})


@app.route("/calls")
def get_calls():
    return jsonify(calls)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)