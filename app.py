from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from datetime import datetime
import json, os

app = Flask(__name__)
app.secret_key = "smartparking_secret_2024"

# ── In-memory data store ──────────────────────────────────────────────────────

PARKING_LOTS = {
    "LOT_A": {
        "name": "Central Plaza Parking",
        "address": "12 MG Road, Chennai",
        "lat": 13.0827, "lng": 80.2707,
        "total": 12,
        "rate": 40,           # ₹/hr
        "slots": {str(i): "available" for i in range(1, 13)},
    },
    "LOT_B": {
        "name": "Tech Park Hub",
        "address": "Old Mahabalipuram Rd, Chennai",
        "lat": 12.9165, "lng": 80.2284,
        "total": 10,
        "rate": 30,
        "slots": {str(i): "available" for i in range(1, 11)},
    },
    "LOT_C": {
        "name": "Airport Express Parking",
        "address": "GST Road, Tambaram",
        "lat": 12.9249, "lng": 80.1000,
        "total": 8,
        "rate": 50,
        "slots": {str(i): "available" for i in range(1, 9)},
    },
}

# Pre-occupy some slots for demo realism
PARKING_LOTS["LOT_A"]["slots"]["2"] = "occupied"
PARKING_LOTS["LOT_A"]["slots"]["5"] = "occupied"
PARKING_LOTS["LOT_B"]["slots"]["1"] = "occupied"
PARKING_LOTS["LOT_B"]["slots"]["3"] = "occupied"
PARKING_LOTS["LOT_C"]["slots"]["7"] = "occupied"

BOOKINGS = {}          # booking_id -> dict
BOOKING_COUNTER = [100]

USERS = {
    "user1": {"password": "pass123", "name": "Arjun Kumar", "bookings": []},
    "admin": {"password": "admin123", "name": "Admin", "bookings": []},
}

ADMIN_USERNAME = "admin"

# ── Helpers ───────────────────────────────────────────────────────────────────

def available_count(lot_id):
    slots = PARKING_LOTS[lot_id]["slots"]
    return sum(1 for s in slots.values() if s == "available")

def new_booking_id():
    BOOKING_COUNTER[0] += 1
    return f"BK{BOOKING_COUNTER[0]}"

# ── Auth routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", lots=PARKING_LOTS, available_count=available_count)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = USERS.get(username)
        if user and user["password"] == password:
            session["username"] = username
            session["name"] = user["name"]
            if username == ADMIN_USERNAME:
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("dashboard"))
        flash("Invalid credentials", "error")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        name = request.form["name"]
        if username in USERS:
            flash("Username already exists", "error")
        else:
            USERS[username] = {"password": password, "name": name, "bookings": []}
            session["username"] = username
            session["name"] = name
            return redirect(url_for("dashboard"))
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# ── User routes ───────────────────────────────────────────────────────────────

@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect(url_for("login"))
    user_bookings = [BOOKINGS[bid] for bid in USERS[session["username"]]["bookings"] if bid in BOOKINGS]
    return render_template("dashboard.html", bookings=user_bookings)

@app.route("/lots")
def lots():
    return render_template("lots.html", lots=PARKING_LOTS, available_count=available_count)

@app.route("/lot/<lot_id>")
def lot_detail(lot_id):
    if lot_id not in PARKING_LOTS:
        return redirect(url_for("lots"))
    lot = PARKING_LOTS[lot_id]
    return render_template("lot_detail.html", lot=lot, lot_id=lot_id, available_count=available_count)

@app.route("/book/<lot_id>/<slot_num>", methods=["GET", "POST"])
def book_slot(lot_id, slot_num):
    if "username" not in session:
        return redirect(url_for("login"))
    lot = PARKING_LOTS.get(lot_id)
    if not lot or lot["slots"].get(slot_num) != "available":
        flash("Slot not available", "error")
        return redirect(url_for("lot_detail", lot_id=lot_id))

    if request.method == "POST":
        hours = int(request.form.get("hours", 1))
        vehicle = request.form.get("vehicle", "").upper()
        bid = new_booking_id()
        booking = {
            "id": bid,
            "lot_id": lot_id,
            "lot_name": lot["name"],
            "slot": slot_num,
            "vehicle": vehicle,
            "hours": hours,
            "amount": hours * lot["rate"],
            "user": session["username"],
            "status": "confirmed",
            "booked_at": datetime.now().strftime("%d %b %Y, %I:%M %p"),
        }
        BOOKINGS[bid] = booking
        USERS[session["username"]]["bookings"].append(bid)
        lot["slots"][slot_num] = "occupied"
        flash(f"Booking confirmed! ID: {bid}", "success")
        return redirect(url_for("booking_confirm", bid=bid))

    return render_template("book.html", lot=lot, lot_id=lot_id, slot_num=slot_num)

@app.route("/booking/<bid>")
def booking_confirm(bid):
    booking = BOOKINGS.get(bid)
    if not booking:
        return redirect(url_for("dashboard"))
    lot = PARKING_LOTS[booking["lot_id"]]
    return render_template("confirm.html", booking=booking, lot=lot)

@app.route("/cancel/<bid>")
def cancel_booking(bid):
    if "username" not in session:
        return redirect(url_for("login"))
    booking = BOOKINGS.get(bid)
    if booking and booking["user"] == session["username"] and booking["status"] == "confirmed":
        PARKING_LOTS[booking["lot_id"]]["slots"][booking["slot"]] = "available"
        booking["status"] = "cancelled"
        flash("Booking cancelled.", "info")
    return redirect(url_for("dashboard"))

# ── Admin routes ──────────────────────────────────────────────────────────────

@app.route("/admin")
def admin_dashboard():
    if session.get("username") != ADMIN_USERNAME:
        return redirect(url_for("login"))
    stats = {
        "total_slots": sum(l["total"] for l in PARKING_LOTS.values()),
        "occupied": sum(1 for l in PARKING_LOTS.values() for s in l["slots"].values() if s == "occupied"),
        "bookings": len(BOOKINGS),
        "revenue": sum(b["amount"] for b in BOOKINGS.values() if b["status"] == "confirmed"),
    }
    return render_template("admin.html", lots=PARKING_LOTS, bookings=BOOKINGS, stats=stats)

@app.route("/admin/toggle/<lot_id>/<slot_num>")
def admin_toggle(lot_id, slot_num):
    if session.get("username") != ADMIN_USERNAME:
        return redirect(url_for("login"))
    slot = PARKING_LOTS[lot_id]["slots"].get(slot_num)
    if slot == "available":
        PARKING_LOTS[lot_id]["slots"][slot_num] = "maintenance"
    elif slot == "maintenance":
        PARKING_LOTS[lot_id]["slots"][slot_num] = "available"
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/release/<lot_id>/<slot_num>")
def admin_release(lot_id, slot_num):
    if session.get("username") != ADMIN_USERNAME:
        return redirect(url_for("login"))
    PARKING_LOTS[lot_id]["slots"][slot_num] = "available"
    return redirect(url_for("admin_dashboard"))

# ── API ───────────────────────────────────────────────────────────────────────

@app.route("/api/lots")
def api_lots():
    data = []
    for lid, lot in PARKING_LOTS.items():
        data.append({
            "id": lid, "name": lot["name"], "address": lot["address"],
            "lat": lot["lat"], "lng": lot["lng"],
            "available": available_count(lid), "total": lot["total"], "rate": lot["rate"],
        })
    return jsonify(data)

if __name__ == "__main__":
    app.run(debug=True)
