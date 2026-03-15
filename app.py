import os
import math
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime, time as dt_time
from urllib import error as url_error
from urllib.request import Request, urlopen

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session
from flask_mysqldb import MySQL

try:
    from openpyxl import load_workbook
except ImportError:  # pragma: no cover - handled by runtime message
    load_workbook = None

load_dotenv(".env")
load_dotenv(".env.local", override=True)

app = Flask(__name__)
app.secret_key = "secret123"
app.config["STATUS_UPDATE_TOKEN"] = os.getenv("STATUS_UPDATE_TOKEN", app.secret_key)

app.config["MYSQL_HOST"] = "208.91.199.36"
app.config["MYSQL_USER"] = "igssewjk_Iiot"
app.config["MYSQL_PASSWORD"] = "Sgi@admin"
app.config["MYSQL_DB"] = "igssewjk_Gggg"

mysql = MySQL(app)
scheduler = BackgroundScheduler()

ALLOWED_UPLOAD_EXTENSIONS = {".xlsx", ".csv"}
PHONE_HEADERS = {"phone", "phone_number", "mobile", "number", "contact", "contact_number"}
TIME_HEADERS = {"time", "schedule_time", "scheduled_at", "call_time", "datetime"}
NAME_HEADERS = {"name", "customer_name", "contact_name", "full_name"}
CALL_RECORD_ACCOUNT_ID = os.getenv("CALL_RECORD_ACCOUNT_ID", "")
CALL_RECORD_AUTH_ID = os.getenv("CALL_RECORD_AUTH_ID", CALL_RECORD_ACCOUNT_ID)
CALL_RECORD_AUTH_TOKEN = os.getenv("CALL_RECORD_AUTH_TOKEN", "")
CALL_RECORD_API_URL = os.getenv("CALL_RECORD_API_URL", "")
SELL_RATE_PER_MINUTE = float(os.getenv("SELL_RATE_PER_MINUTE", "5"))
WALLET_RECHARGE_URL = os.getenv("WALLET_RECHARGE_URL", "https://rzp.io/rzp/jey2OJZ")
MIN_RECHARGE_AMOUNT = float(os.getenv("MIN_RECHARGE_AMOUNT", "30"))
MAX_RECHARGE_AMOUNT = float(os.getenv("MAX_RECHARGE_AMOUNT", "10000"))


def login_required():
    if "user" not in session:
        return False
    return True


def get_table_columns(table_name):
    cur = mysql.connection.cursor()
    try:
        cur.execute(f"SHOW COLUMNS FROM {table_name}")
        columns = {row[0] for row in cur.fetchall()}
    except Exception:
        columns = set()
    finally:
        cur.close()
    return columns


def get_agent_call_columns():
    return get_table_columns("agent_calls")


def get_agent_checker_columns():
    return get_table_columns("agent_checker")


def get_wallet_transaction_columns():
    return get_table_columns("agent_wallet_transactions")


def format_dt(value):
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value or "")


def normalize_header(value):
    return str(value or "").strip().lower().replace(" ", "_")


def normalize_phone(value):
    raw = str(value or "").strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    return digits


def parse_schedule_value(value):
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, date):
        return datetime.combine(value, dt_time(hour=9, minute=0))

    text = str(value).strip()
    if not text:
        return None

    formats = [
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y %I:%M %p",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    raise ValueError(f"Invalid schedule time: {text}")


def create_call(phone, schedule_time, user_id, message, contact_name=None):
    columns = get_agent_call_columns()
    insert_columns = ["user_id", "phone", "schedule_time", "status"]
    placeholders = ["%s", "%s", "%s", "%s"]
    values = [user_id, phone, schedule_time, "scheduled"]

    if "message" in columns:
        insert_columns.append("message")
        placeholders.append("%s")
        values.append(message[:255])

    if contact_name and "customer_name" in columns:
        insert_columns.append("customer_name")
        placeholders.append("%s")
        values.append(contact_name[:120])

    cur = mysql.connection.cursor()
    cur.execute(
        f"INSERT INTO agent_calls({', '.join(insert_columns)}) "
        f"VALUES({', '.join(placeholders)})",
        tuple(values),
    )
    call_id = cur.lastrowid
    mysql.connection.commit()
    cur.close()
    return call_id


def update_call_record(call_id, status, message=None):
    columns = get_agent_call_columns()
    updates = ["status=%s"]
    values = [status]

    if message is not None and "message" in columns:
        updates.append("message=%s")
        values.append(message[:255])

    if "updated_at" in columns:
        updates.append("updated_at=NOW()")

    values.append(call_id)

    cur = mysql.connection.cursor()
    cur.execute(
        f"UPDATE agent_calls SET {', '.join(updates)} WHERE id=%s",
        tuple(values),
    )
    mysql.connection.commit()
    cur.close()


def fetch_calls_for_user(user_id, limit=None):
    columns = get_agent_call_columns()
    select_fields = ["id", "phone", "schedule_time", "status"]

    if "message" in columns:
        select_fields.append("message")
    else:
        select_fields.append("'' AS message")

    if "updated_at" in columns:
        select_fields.append("updated_at")
    else:
        select_fields.append("schedule_time AS updated_at")

    if "customer_name" in columns:
        select_fields.append("customer_name")
    else:
        select_fields.append("'' AS customer_name")

    query = (
        f"SELECT {', '.join(select_fields)} "
        "FROM agent_calls WHERE user_id=%s ORDER BY schedule_time DESC, id DESC"
    )

    if limit:
        query += f" LIMIT {int(limit)}"

    cur = mysql.connection.cursor()
    cur.execute(query, (user_id,))
    rows = cur.fetchall()
    cur.close()

    calls = []
    for row in rows:
        calls.append(
            {
                "id": row[0],
                "phone": row[1],
                "time": format_dt(row[2]),
                "status": row[3],
                "message": row[4] or "",
                "updated_at": format_dt(row[5]),
                "customer_name": row[6] or "",
            }
        )

    return calls


def get_current_agent_profile(user_id):
    columns = get_agent_checker_columns()
    if not columns:
        return None

    cur = mysql.connection.cursor()
    cur.execute(
        """
        SELECT id, credential_id, assigned_number, sip_user, sip_pass, active, is_approved, approved_at
        FROM agent_checker
        WHERE approved_user_id=%s AND is_approved=1
        ORDER BY approved_at DESC, id DESC
        LIMIT 1
        """,
        (user_id,),
    )
    row = cur.fetchone()
    cur.close()

    if not row:
        return None

    return {
        "id": row[0],
        "credential_id": row[1],
        "assigned_number": row[2],
        "sip_user": row[3],
        "sip_pass": row[4],
        "active": bool(row[5]),
        "is_approved": bool(row[6]),
        "approved_at": format_dt(row[7]),
    }


def approve_agent_for_user(user_id, credential_id, credential_password):
    if not get_agent_checker_columns():
        return False, "Table `agent_checker` not found. Please create it first."

    cur = mysql.connection.cursor()
    cur.execute(
        """
        SELECT id, credential_id, credential_password, assigned_number, sip_user, sip_pass, active, approved_user_id
        FROM agent_checker
        WHERE credential_id=%s
        LIMIT 1
        """,
        (credential_id,),
    )
    row = cur.fetchone()

    if not row:
        cur.close()
        return False, "Credential ID not found in agent_checker."

    if str(row[2]) != str(credential_password):
        cur.close()
        return False, "Credential password does not match."

    if not row[6]:
        cur.close()
        return False, "This agent credential is inactive."

    if row[7] and int(row[7]) != int(user_id):
        cur.close()
        return False, "This credential is already approved for another user."

    cur.execute(
        """
        UPDATE agent_checker
        SET is_approved=0, approved_user_id=NULL, approved_at=NULL
        WHERE approved_user_id=%s
        """,
        (user_id,),
    )
    cur.execute(
        """
        UPDATE agent_checker
        SET is_approved=1, approved_user_id=%s, approved_at=NOW()
        WHERE id=%s
        """,
        (user_id, row[0]),
    )
    mysql.connection.commit()
    cur.close()
    return True, "Agent approved successfully."


def fetch_live_call_records():
    if not CALL_RECORD_AUTH_ID or not CALL_RECORD_AUTH_TOKEN or not CALL_RECORD_API_URL:
        raise ValueError("Call record API credentials are missing.")

    req = Request(
        CALL_RECORD_API_URL,
        headers={
            "X-Auth-ID": CALL_RECORD_AUTH_ID,
            "X-Auth-Token": CALL_RECORD_AUTH_TOKEN,
            "Content-Type": "application/json",
        },
    )

    try:
        with urlopen(req, timeout=20) as response:
            payload = response.read().decode("utf-8")
    except url_error.URLError as exc:
        raise ValueError(f"Unable to load call detail records: {exc}") from exc

    import json

    data = json.loads(payload)
    return data.get("data", []) if isinstance(data, dict) else []


def get_wallet_summary(user_id, used_amount):
    columns = get_wallet_transaction_columns()
    if not columns:
        return {
            "wallet_enabled": False,
            "total_recharged": 0.0,
            "remaining_balance": 0.0,
            "used_amount": round(used_amount, 2),
        }

    cur = mysql.connection.cursor()
    cur.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM agent_wallet_transactions
        WHERE user_id=%s AND transaction_type='recharge'
        """,
        (user_id,),
    )
    total_recharged = float(cur.fetchone()[0] or 0)
    cur.close()

    return {
        "wallet_enabled": True,
        "total_recharged": round(total_recharged, 2),
        "remaining_balance": round(total_recharged - used_amount, 2),
        "used_amount": round(used_amount, 2),
    }


def add_wallet_recharge(user_id, amount, note="Manual wallet recharge"):
    columns = get_wallet_transaction_columns()
    if not columns:
        return False, "Please create `agent_wallet_transactions` table first."

    cur = mysql.connection.cursor()
    cur.execute(
        """
        INSERT INTO agent_wallet_transactions(user_id, amount, transaction_type, note)
        VALUES(%s, %s, 'recharge', %s)
        """,
        (user_id, amount, note),
    )
    mysql.connection.commit()
    cur.close()
    return True, "Wallet recharged successfully."


def get_filtered_call_records(user_id):
    scheduled_calls = fetch_calls_for_user(user_id)
    approved_agent = get_current_agent_profile(user_id)
    scheduled_numbers = {normalize_phone(call["phone"]) for call in scheduled_calls if call.get("phone")}
    call_names = {
        normalize_phone(call["phone"]): (call.get("customer_name") or "")
        for call in scheduled_calls
        if call.get("phone")
    }

    if not scheduled_numbers:
        wallet = get_wallet_summary(user_id, 0)
        return {
            "summary": {
                "total_records": 0,
                "talk_minutes": 0,
                "billable_minutes": 0,
                "billed_amount": 0,
                "wallet_recharged": wallet["total_recharged"],
                "wallet_remaining": wallet["remaining_balance"],
            },
            "customer_summary": [],
            "records": [],
            "wallet": wallet,
        }

    assigned_number = normalize_phone(approved_agent["assigned_number"]) if approved_agent else ""
    records = []
    customer_summary = defaultdict(
        lambda: {
            "customer_name": "",
            "phone": "",
            "call_count": 0,
            "talk_minutes": 0.0,
            "billable_minutes": 0,
            "billed_amount": 0.0,
        }
    )

    for record in fetch_live_call_records():
        destination = normalize_phone(record.get("destination_number"))
        caller = normalize_phone(record.get("caller_id_number"))

        if destination not in scheduled_numbers:
            continue

        if assigned_number and caller and caller != assigned_number:
            continue

        duration_seconds = int(record.get("duration") or 0)
        talk_minutes = round(duration_seconds / 60, 2)
        billable_minutes = math.ceil(duration_seconds / 60) if duration_seconds > 0 else 0
        billed_amount = round(billable_minutes * SELL_RATE_PER_MINUTE, 2)
        customer_name = call_names.get(destination, "")
        status_text = record.get("hangup_cause") or "UNKNOWN"

        item = {
            "id": record.get("id"),
            "caller": record.get("caller_id_number") or "",
            "phone": record.get("destination_number") or "",
            "customer_name": customer_name,
            "duration_seconds": duration_seconds,
            "talk_minutes": talk_minutes,
            "billable_minutes": billable_minutes,
            "billed_amount": billed_amount,
            "status": status_text,
            "start_time": record.get("start_time") or "",
        }
        records.append(item)

        summary_key = destination
        customer_summary[summary_key]["customer_name"] = customer_name or customer_summary[summary_key]["customer_name"]
        customer_summary[summary_key]["phone"] = item["phone"]
        customer_summary[summary_key]["call_count"] += 1
        customer_summary[summary_key]["talk_minutes"] = round(
            customer_summary[summary_key]["talk_minutes"] + talk_minutes, 2
        )
        customer_summary[summary_key]["billable_minutes"] += billable_minutes
        customer_summary[summary_key]["billed_amount"] = round(
            customer_summary[summary_key]["billed_amount"] + billed_amount, 2
        )

    records.sort(key=lambda row: row["start_time"], reverse=True)
    summary_rows = sorted(customer_summary.values(), key=lambda row: row["billed_amount"], reverse=True)
    total_talk_minutes = round(sum(row["talk_minutes"] for row in records), 2)
    total_billable_minutes = sum(row["billable_minutes"] for row in records)
    total_billed_amount = round(sum(row["billed_amount"] for row in records), 2)
    wallet = get_wallet_summary(user_id, total_billed_amount)

    return {
        "summary": {
            "total_records": len(records),
            "talk_minutes": total_talk_minutes,
            "billable_minutes": total_billable_minutes,
            "billed_amount": total_billed_amount,
            "wallet_recharged": wallet["total_recharged"],
            "wallet_remaining": wallet["remaining_balance"],
        },
        "customer_summary": summary_rows,
        "records": records,
        "wallet": wallet,
    }


def get_dashboard_payload(user_id):
    calls = fetch_calls_for_user(user_id, limit=10)
    all_calls = fetch_calls_for_user(user_id)
    approved_agent = get_current_agent_profile(user_id)
    try:
        call_record_data = get_filtered_call_records(user_id)
    except ValueError:
        call_record_data = {
            "summary": {
                "talk_minutes": 0,
                "billable_minutes": 0,
                "billed_amount": 0,
                "wallet_recharged": 0,
                "wallet_remaining": 0,
            }
        }

    live_statuses = {"calling", "ringing"}
    no_response_statuses = {"not_picked", "no_response"}
    failed_statuses = {"failed", "error", "rejected", "invalid"}

    stats = {
        "total": len(all_calls),
        "scheduled": sum(1 for call in all_calls if call["status"] == "scheduled"),
        "live": sum(1 for call in all_calls if call["status"] in live_statuses),
        "answered": sum(1 for call in all_calls if call["status"] == "answered"),
        "no_response": sum(1 for call in all_calls if call["status"] in no_response_statuses),
        "failed": sum(1 for call in all_calls if call["status"] in failed_statuses),
        "approved": bool(approved_agent),
        "assigned_number": approved_agent["assigned_number"] if approved_agent else "",
        "credential_id": approved_agent["credential_id"] if approved_agent else "",
        "talk_minutes": call_record_data["summary"]["talk_minutes"],
        "wallet_remaining": call_record_data["summary"]["wallet_remaining"],
    }

    if stats["total"]:
        stats["success_rate"] = round((stats["answered"] / stats["total"]) * 100, 1)
    else:
        stats["success_rate"] = 0

    return {
        "stats": stats,
        "calls": calls,
        "agent": approved_agent,
        "call_record_summary": call_record_data["summary"],
    }


def schedule_call_job(call_id, phone, schedule_time):
    scheduler.add_job(
        run_call,
        "date",
        run_date=schedule_time,
        args=[call_id, phone],
        id=f"call-{call_id}",
        replace_existing=True,
    )


def run_call(call_id, phone):
    with app.app_context():
        update_call_record(call_id, "calling", "Dispatching AI agent.")

    result = subprocess.run(
        [sys.executable, "make_call.py", "--to", phone, "--call-id", str(call_id)],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )

    if result.returncode != 0:
        error_text = (result.stderr or result.stdout or "Call dispatch failed.").strip()
        with app.app_context():
            update_call_record(call_id, "failed", error_text)


def require_approved_agent():
    if not login_required():
        return None, (jsonify({"ok": False, "error": "Unauthorized"}), 401)

    agent = get_current_agent_profile(session["user"])
    if not agent:
        return None, (
            jsonify({"ok": False, "error": "Please approve your agent credential from Settings first."}),
            403,
        )

    return agent, None


def schedule_single_call(user_id, phone, schedule_time, contact_name=None):
    call_id = create_call(
        phone=phone,
        schedule_time=schedule_time,
        user_id=user_id,
        message="Waiting for scheduled time.",
        contact_name=contact_name,
    )
    schedule_call_job(call_id, phone, schedule_time)
    return call_id


def parse_excel_rows(uploaded_file, default_schedule_time):
    if load_workbook is None:
        raise ValueError("openpyxl is not installed. Please install requirements first.")

    workbook = load_workbook(uploaded_file, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))

    if not rows:
        return []

    headers = [normalize_header(value) for value in rows[0]]
    phone_index = next((i for i, value in enumerate(headers) if value in PHONE_HEADERS), None)
    time_index = next((i for i, value in enumerate(headers) if value in TIME_HEADERS), None)
    name_index = next((i for i, value in enumerate(headers) if value in NAME_HEADERS), None)

    if phone_index is None:
        raise ValueError("Excel file must contain a phone column like phone, mobile, or phone_number.")

    parsed_rows = []

    for raw_row in rows[1:]:
        if not raw_row:
            continue

        phone = str(raw_row[phone_index] or "").strip()
        if not phone:
            continue

        row_time = raw_row[time_index] if time_index is not None and time_index < len(raw_row) else None
        schedule_time = parse_schedule_value(row_time) if row_time not in (None, "") else default_schedule_time
        if schedule_time is None:
            raise ValueError(f"Schedule time missing for phone {phone}.")

        contact_name = ""
        if name_index is not None and name_index < len(raw_row):
            contact_name = str(raw_row[name_index] or "").strip()

        parsed_rows.append(
            {
                "phone": phone,
                "schedule_time": schedule_time,
                "customer_name": contact_name,
            }
        )

    return parsed_rows


@app.route("/")
def home():
    if "user" in session:
        return redirect("/dashboard")
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT * FROM agent_users WHERE email=%s AND password=%s",
            (email, password),
        )
        user = cur.fetchone()
        cur.close()

        if user:
            session["user"] = user[0]
            return redirect("/dashboard")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO agent_users(name,email,password) VALUES(%s,%s,%s)",
            (name, email, password),
        )
        mysql.connection.commit()
        cur.close()

        return redirect("/login")

    return render_template("register.html")


@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect("/login")

    payload = get_dashboard_payload(session["user"])
    return render_template("dashboard.html", payload=payload)


@app.route("/dashboard_data")
def dashboard_data():
    if not login_required():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    return jsonify(get_dashboard_payload(session["user"]))


@app.route("/call-detail-record")
def call_detail_record():
    if not login_required():
        return redirect("/login")

    try:
        payload = get_filtered_call_records(session["user"])
        load_error = ""
    except ValueError as exc:
        payload = {
            "summary": {
                "total_records": 0,
                "talk_minutes": 0,
                "billable_minutes": 0,
                "billed_amount": 0,
                "wallet_recharged": 0,
                "wallet_remaining": 0,
            },
            "customer_summary": [],
            "records": [],
            "wallet": {"wallet_enabled": bool(get_wallet_transaction_columns())},
        }
        load_error = str(exc)

    return render_template("call_detail_record.html", payload=payload, load_error=load_error)


@app.route("/call_detail_record_data")
def call_detail_record_data():
    if not login_required():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    try:
        return jsonify({"ok": True, "payload": get_filtered_call_records(session["user"])})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502


@app.route("/wallet_recharge", methods=["POST"])
def wallet_recharge():
    if not login_required():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    amount_raw = (request.get_json(silent=True) or {}).get("amount")
    try:
        amount = float(amount_raw)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Please enter a valid recharge amount."}), 400

    if amount <= 0:
        return jsonify({"ok": False, "error": "Recharge amount must be greater than zero."}), 400

    success, message = add_wallet_recharge(session["user"], amount)
    status = 200 if success else 400
    return jsonify({"ok": success, "message": message}), status


@app.route("/outbound", methods=["GET", "POST"])
def outbound():
    if not login_required():
        return redirect("/login")

    approved_agent = get_current_agent_profile(session["user"])

    if request.method == "POST":
        if not approved_agent:
            return redirect("/settings")

        phone = request.form["phone"].strip()
        schedule_time = parse_schedule_value(request.form["time"])
        schedule_single_call(session["user"], phone, schedule_time)
        return redirect("/outbound")

    return render_template("outbound.html", approved_agent=approved_agent)


@app.route("/schedule_call", methods=["POST"])
def schedule_call():
    approved_agent, error = require_approved_agent()
    if error:
        return error

    data = request.get_json(silent=True) or {}
    phone = (data.get("phone") or "").strip()
    time_value = (data.get("time") or "").strip()

    if not phone or not time_value:
        return jsonify({"ok": False, "error": "Phone and time are required."}), 400

    try:
        schedule_time = parse_schedule_value(time_value)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    call_id = schedule_single_call(session["user"], phone, schedule_time)

    return jsonify(
        {
            "ok": True,
            "call_id": call_id,
            "status": "scheduled",
            "message": f"Call scheduled with approved agent {approved_agent['credential_id']}.",
        }
    )


@app.route("/upload_contacts", methods=["POST"])
def upload_contacts():
    _, error = require_approved_agent()
    if error:
        return error

    if "file" not in request.files:
        return jsonify({"ok": False, "error": "Please upload an Excel file."}), 400

    uploaded_file = request.files["file"]
    extension = os.path.splitext(uploaded_file.filename or "")[1].lower()

    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        return jsonify({"ok": False, "error": "Only .xlsx or .csv files are supported."}), 400

    default_time_raw = (request.form.get("default_time") or "").strip()
    default_schedule_time = None
    if default_time_raw:
        try:
            default_schedule_time = parse_schedule_value(default_time_raw)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    try:
        if extension == ".csv":
            import csv
            import io

            stream = io.StringIO(uploaded_file.stream.read().decode("utf-8-sig"))
            reader = csv.DictReader(stream)
            parsed_rows = []
            for row in reader:
                normalized = {normalize_header(key): value for key, value in row.items()}
                phone = str(
                    next((normalized[key] for key in normalized if key in PHONE_HEADERS), "") or ""
                ).strip()
                if not phone:
                    continue

                time_value = next((normalized[key] for key in normalized if key in TIME_HEADERS), "")
                name_value = next((normalized[key] for key in normalized if key in NAME_HEADERS), "")
                schedule_time = parse_schedule_value(time_value) if time_value else default_schedule_time
                if schedule_time is None:
                    raise ValueError(f"Schedule time missing for phone {phone}.")

                parsed_rows.append(
                    {
                        "phone": phone,
                        "schedule_time": schedule_time,
                        "customer_name": str(name_value or "").strip(),
                    }
                )
        else:
            parsed_rows = parse_excel_rows(uploaded_file, default_schedule_time)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    if not parsed_rows:
        return jsonify({"ok": False, "error": "No valid contacts found in the uploaded file."}), 400

    scheduled_count = 0
    for row in parsed_rows:
        schedule_single_call(
            user_id=session["user"],
            phone=row["phone"],
            schedule_time=row["schedule_time"],
            contact_name=row.get("customer_name"),
        )
        scheduled_count += 1

    return jsonify(
        {
            "ok": True,
            "scheduled_count": scheduled_count,
            "message": f"{scheduled_count} calls uploaded and scheduled successfully.",
        }
    )


@app.route("/calls")
def calls():
    if not login_required():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    return jsonify(fetch_calls_for_user(session["user"]))


@app.route("/internal/call_status", methods=["POST"])
def internal_call_status():
    token = request.headers.get("X-Status-Token")
    if token != app.config["STATUS_UPDATE_TOKEN"]:
        return jsonify({"ok": False, "error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    call_id = data.get("call_id")
    status = (data.get("status") or "").strip()
    message = (data.get("message") or "").strip()

    if not call_id or not status:
        return jsonify({"ok": False, "error": "call_id and status are required."}), 400

    update_call_record(call_id, status, message or None)
    return jsonify({"ok": True})


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if not login_required():
        return redirect("/login")

    message = ""
    message_type = ""

    if request.method == "POST":
        credential_id = request.form.get("credential_id", "").strip()
        credential_password = request.form.get("credential_password", "").strip()

        if not credential_id or not credential_password:
            message = "Please enter credential ID and password."
            message_type = "error"
        else:
            success, message = approve_agent_for_user(session["user"], credential_id, credential_password)
            message_type = "success" if success else "error"

    profile = get_current_agent_profile(session["user"])
    return render_template(
        "settings.html",
        profile=profile,
        message=message,
        message_type=message_type,
    )


if __name__ == "__main__":
    scheduler.start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)