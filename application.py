import os
import requests
from functools import wraps

from flask import Flask, session, redirect, url_for, request, render_template, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


def apology(message):
    return render_template("apology.html", apology=message)


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    elif request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).rowcount != 0:
            return apology("Username taken")

        db.execute("INSERT INTO users (username, password) VALUES (:username, :password)",
                   {"username": username, "password": password})
        db.commit()

        return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()
    if request.method == "GET":
        return render_template("login.html")
    elif request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).rowcount != 0:
            user = db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).fetchone()
            if username == user["username"] and password == user["password"]:
                session["user_id"] = user["id"]
                return redirect(url_for("index"))
            else:
                return apology("Wrong username or password")
        else:
            return apology("Wrong username or password")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
    if request.method == "GET":
        return render_template("search.html")
    elif request.method == "POST":
        isbn = request.form.get("isbn")
        title = request.form.get("title")
        author = request.form.get("author")
        books = db.execute("SELECT * FROM books WHERE isbn = :isbn OR title = :title OR author = :author",
                           {"isbn": isbn, "title": title, "author": author})
        return render_template("listbooks.html", books=books)


@app.route("/review/<isbn>", methods=["GET", "POST"])
@login_required
def review(isbn):
    reviews = db.execute("SELECT * FROM books LEFT JOIN reviews ON reviews.book_id = books.id WHERE isbn = :isbn",
                         {"isbn": isbn}).fetchall()
    book = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
    json = requests.get("https://www.goodreads.com/book/review_counts.json",
                        params={"key": "iIEWEniGZPHuDH04oIpRg", "isbns": isbn}).json()
    details = json["books"][0]
    rating = request.form.get("rating")
    if request.method == "GET":
        return render_template("review.html", reviews=reviews, book=book, details=details)
    elif request.method == "POST":
        review = request.form.get("review")
        book_id = book["id"]
        user_id = session["user_id"]
        if db.execute(
                "SELECT review FROM books LEFT JOIN reviews ON reviews.book_id = books.id WHERE book_id = :book_id AND user_id = :user_id",
                {"book_id": book_id, "user_id": user_id}).rowcount != 0:
            return apology("You've reviewed this book")
        else:
            db.execute("INSERT INTO reviews (user_id, book_id, review, rating) VALUES (:user_id, :book_id, :rv, :rt)",
                       {"user_id": user_id, "book_id": book_id, "rv": review, "rt": rating})
            db.commit()
            return redirect(url_for("review", isbn=isbn))


@app.route("/api/<isbn>")
def api(isbn):
    book = db.execute("SELECT * FROM books  WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
    review_counts = db.execute("SELECT COUNT(review) FROM reviews WHERE book_id = :book_id",
                               {"book_id": book["id"]}).fetchone()
    avg_rating = db.execute("SELECT AVG(rating) FROM reviews WHERE book_id = :book_id",
                            {"book_id": book["id"]}).fetchone()
    json = {
        "title": book["title"],
        "author": book["author"],
        "year": book["year"],
        "isbn": book["isbn"],
        "review_count": review_counts["count"],
        "average_score": float(avg_rating["avg"])
    }
    return jsonify(json)
