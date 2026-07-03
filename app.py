import os
from datetime import datetime

import requests
from bson import ObjectId
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from pymongo import MongoClient
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "elyra-dev-secret")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:1b")

mongo_client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/"))
db = mongo_client[os.getenv("MONGO_DB", "elyra_db")]

users_collection = db["users"]
flights_collection = db["flights"]
bookings_collection = db["bookings"]
chat_logs_collection = db["chat_logs"]


SAMPLE_FLIGHTS = [
    {
        "airline": "Elyra Air",
        "from": "Delhi",
        "to": "Mumbai",
        "depart": "08:15",
        "arrive": "10:25",
        "date": "2026-07-18",
        "economy": 5499,
        "business": 16499,
        "type": "Domestic",
    },
    {
        "airline": "Elyra Air",
        "from": "Delhi",
        "to": "Bengaluru",
        "depart": "13:40",
        "arrive": "16:25",
        "date": "2026-07-18",
        "economy": 6799,
        "business": 19499,
        "type": "Domestic",
    },
    {
        "airline": "Elyra Air",
        "from": "Mumbai",
        "to": "Goa",
        "depart": "09:30",
        "arrive": "10:45",
        "date": "2026-07-19",
        "economy": 3999,
        "business": 10999,
        "type": "Domestic",
    },
    {
        "airline": "Elyra Air",
        "from": "Kolkata",
        "to": "Delhi",
        "depart": "18:05",
        "arrive": "20:25",
        "date": "2026-07-20",
        "economy": 6299,
        "business": 17999,
        "type": "Domestic",
    },
    {
        "airline": "Elyra Air",
        "from": "Chennai",
        "to": "Singapore",
        "depart": "23:15",
        "arrive": "06:10",
        "date": "2026-07-21",
        "economy": 18499,
        "business": 52999,
        "type": "International",
    },
    {
        "airline": "Elyra Air",
        "from": "Delhi",
        "to": "Dubai",
        "depart": "04:25",
        "arrive": "07:05",
        "date": "2026-07-22",
        "economy": 21999,
        "business": 68999,
        "type": "International",
    },
    {
        "airline": "Elyra Air",
        "from": "Bengaluru",
        "to": "London",
        "depart": "02:10",
        "arrive": "11:55",
        "date": "2026-07-23",
        "economy": 48999,
        "business": 149999,
        "type": "International",
    },
]


def seed_flights():
    if flights_collection.count_documents({}) == 0:
        flights_collection.insert_many(SAMPLE_FLIGHTS)


def get_flight(flight_id):
    try:
        return flights_collection.find_one({"_id": ObjectId(flight_id)})
    except Exception:
        return None


def serialize_flight(flight):
    flight["_id"] = str(flight["_id"])
    return flight


def build_flight_context():
    flights = list(flights_collection.find().sort("date", 1))
    return "\n".join(
        f"{flight['from']} to {flight['to']} on {flight['date']} at {flight['depart']}: "
        f"Economy Rs {flight['economy']}, Business Rs {flight['business']}, {flight['type']}"
        for flight in flights
    )


def fallback_chat(message):
    text = message.lower()
    flights = list(flights_collection.find())

    for flight in flights:
        if flight["from"].lower() in text and flight["to"].lower() in text:
            return (
                f"Yes, Elyra has a {flight['type'].lower()} flight from {flight['from']} to {flight['to']} "
                f"on {flight['date']} at {flight['depart']}. Economy is Rs {flight['economy']:,} "
                f"and Business is Rs {flight['business']:,}."
            )

    if "international" in text:
        routes = sorted({flight["to"] for flight in flights if flight.get("type") == "International"})
        return f"Elyra currently has demo international flights to {', '.join(routes)}."

    if "domestic" in text:
        routes = sorted({f"{flight['from']} to {flight['to']}" for flight in flights if flight.get("type") == "Domestic"})
        return f"Elyra domestic demo routes include {', '.join(routes)}."

    if "price" in text or "fare" in text or "cost" in text:
        return "Elyra demo fares start from Rs 3,999 for domestic flights and Rs 18,499 for international flights."

    return "I can help with Elyra routes, prices, availability, and economy or business class options."


@app.route("/")
def home():
    featured_flights = list(flights_collection.find().sort("economy", 1).limit(3))
    return render_template("home.html", featured_flights=featured_flights)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if users_collection.find_one({"email": email}):
            return render_template("signup.html", error="An account with this email already exists.")

        users_collection.insert_one(
            {
                "name": name,
                "email": email,
                "password": generate_password_hash(password),
                "created_at": datetime.now(),
            }
        )
        session["user"] = email
        session["name"] = name
        return redirect(url_for("book"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = users_collection.find_one({"email": email})

        if not user or not check_password_hash(user["password"], password):
            return render_template("login.html", error="Invalid email or password.")

        session["user"] = user["email"]
        session["name"] = user.get("name", "Traveler")
        return redirect(url_for("book"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/book")
def book():
    flights = list(flights_collection.find())
    cities = sorted({flight["from"] for flight in flights} | {flight["to"] for flight in flights})
    return render_template("book.html", cities=cities)


@app.route("/results")
def results():
    origin = request.args.get("from", "")
    destination = request.args.get("to", "")
    travel_date = request.args.get("date", "")
    return_date = request.args.get("return_date", "")
    trip_type = request.args.get("trip_type", "one-way")

    matches = list(
        flights_collection.find(
            {
                "from": origin,
                "to": destination,
                "date": travel_date,
            }
        ).sort("economy", 1)
    )

    if not matches:
        matches = list(
            flights_collection.find(
                {
                    "from": origin,
                    "to": destination,
                }
            ).sort("economy", 1)
        )

    return render_template(
        "results.html",
        flights=matches,
        origin=origin,
        destination=destination,
        travel_date=travel_date,
        return_date=return_date,
        trip_type=trip_type,
    )


@app.route("/select/<flight_id>", methods=["GET", "POST"])
def select_class(flight_id):
    flight = get_flight(flight_id)
    if not flight:
        return redirect(url_for("book"))

    if request.method == "POST":
        travel_class = request.form.get("travel_class", "economy")
        return redirect(url_for("passenger", flight_id=flight_id, travel_class=travel_class))

    return render_template("select_class.html", flight=flight)


@app.route("/passenger/<flight_id>", methods=["GET", "POST"])
def passenger(flight_id):
    flight = get_flight(flight_id)
    travel_class = request.args.get("travel_class", "economy")

    if not flight:
        return redirect(url_for("book"))

    price = flight["business"] if travel_class == "business" else flight["economy"]

    if request.method == "POST":
        booking = {
            "user_email": session.get("user"),
            "name": request.form.get("name", "").strip(),
            "email": request.form.get("email", "").strip().lower(),
            "phone": request.form.get("phone", "").strip(),
            "flight_id": flight["_id"],
            "flight": {
                "airline": flight["airline"],
                "from": flight["from"],
                "to": flight["to"],
                "depart": flight["depart"],
                "arrive": flight["arrive"],
                "date": flight["date"],
                "type": flight["type"],
            },
            "travel_class": travel_class.title(),
            "price": price,
            "payment_status": "Paid",
            "created_at": datetime.now(),
        }

        bookings_collection.insert_one(booking)
        return render_template("confirmation.html", booking=booking)

    return render_template("passenger.html", flight=flight, travel_class=travel_class, price=price)


@app.post("/chat")
def chat():
    user_message = request.json.get("message", "").strip()

    if not user_message:
        return jsonify({"reply": "Please ask me something about Elyra flights."})

    prompt = f"""
You are Elyra's airline assistant.
Elyra is a premium airline offering reasonable domestic and international flights from India.
Answer customer questions about routes, prices, availability, and cabin classes.
Use only the flight data below.
If a route is not available, say it is not available in the current demo data and suggest using the booking search.
Keep answers short, friendly, and useful.

Flight data:
{build_flight_context()}

Customer question:
{user_message}
"""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
            },
            timeout=20,
        )
        response.raise_for_status()
        reply = response.json().get("response", "Sorry, I could not generate a response.").strip()
    except requests.RequestException:
        reply = fallback_chat(user_message)

    chat_logs_collection.insert_one(
        {
            "message": user_message,
            "reply": reply,
            "model": OLLAMA_MODEL,
            "created_at": datetime.now(),
        }
    )

    return jsonify({"reply": reply})


if __name__ == "__main__":
    seed_flights()
    app.run(debug=True)
