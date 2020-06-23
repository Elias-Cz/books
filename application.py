import os
import requests
from flask import Flask
from flask import Flask, flash, redirect, jsonify, session, url_for, logging, render_template, request
from flask_session import Session
from sqlalchemy import create_engine
from passlib.hash import pbkdf2_sha256
from sqlalchemy.orm import scoped_session, sessionmaker

# key: w9Np63RHCDhV5fIkdoF43w
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

# Function that gets used a few times for submitting reviews

def stuff(isbn):
    name = session['username']
    ok = db.execute("SELECT rev_user FROM reviews WHERE isbn = :isbn", {"isbn": isbn})
    print(ok)
    if request.method == 'POST' and ok != None:
        review_target = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
        title = review_target.title
        isbn = review_target.isbn
        author = review_target.author
        year = review_target.year
        rev = request.form.get("review")
        str = request.form.get("star") + "/5"
        username = session["username"]
        db.execute("INSERT INTO reviews (rev_user, review, isbn, stars) VALUES (:username, :rev, :isbn, :str)", {"username": username, "rev": rev, "isbn": isbn, "str": str})
        db.commit()
        flash("your review has been submitted")
    elif ok == None:
        flash("You have already submitted a review!")

# Default route. Prompts user to either log in or register as a user.

@app.route('/', methods=['POST', 'GET'])
def index():
    if "logged_in" in session == False or "logged_in" in session == None:
        return render_template('login.html')
    elif "logged_in" in session == True:
        return redirect(url_for('home'))
    return render_template('index.html')

# Register route. Simple account creation form. Keeps track of users in sql table "users"

@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")
        passwordr = request.form.get("passwordr")
        if password != passwordr or password is None or passwordr is None:
            flash("Password don't match")
            return render_template('register.html')
        hash = pbkdf2_sha256.hash(password)
        db.execute("INSERT INTO users (username, password) VALUES (:username, :hash)",
                    {"username": username, "hash": hash})
        db.commit()
        "logged_in" in session == True
        "username" in session == username
        session['username'] = request.form.get("username")
        #flash("Register successful")
        return redirect(url_for('home', username=username))
    return render_template("register.html")

# Simple login form which references sql table "users"

@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        ck = db.execute("SELECT id, password, username FROM users WHERE username = :username", {"username": username}).fetchone()
        if ck == None:
            flash("User not found")
            return render_template('login.html')
        db_hash = ck.password
        user_id = ck.id
        username = ck.username
        print(username)
        if pbkdf2_sha256.verify(password, db_hash):
            "logged_in" in session == True
            "user_id" in session == user_id
            session['username'] = request.form.get("username")
            return redirect(url_for('home', username=username))
        else:
            flash("wrong password!")
            return render_template('login.html')
    return render_template('login.html')

# Logout button which is present on navbar at all times

@app.route('/logout', methods=["POST", "GET"])
def logout():
    session.clear()
    "logged_in" in session == False
    "user_id" in session == None
    flash("logged out")
    return render_template('index.html')

# Home route, which displays users name and from which users can search for books

@app.route('/home', methods=['POST', 'GET'])
def home():
    username = request.args['username']
    if request.method == "POST":
        res = '%'+ request.form.get('book') + '%'
        return redirect(url_for('results', res=res))
    return render_template("home.html", username=username)

# Once user has searched for a book, they are taken to this route, which displays related results and reviews, plus extra info
@app.route('/results', methods=['POST', 'GET'])
def results():
    res = request.args['res']
    rows = db.execute("SELECT * FROM books WHERE LOWER(title) LIKE LOWER(:res) OR LOWER(author) LIKE LOWER(:res) OR year LIKE :res OR isbn LIKE :res LIMIT 5", {"res": res}).fetchall()
    username = session["username"]
    if not rows:
        flash("book not found")
        return redirect(url_for("home", username=username))
    else:
        return render_template("results.html", rows=rows, username=username)


@app.route('/results=<book>', methods=['POST', 'GET'])
def book(book):
    name = session["username"]
    isbn = book
    print(isbn)
    br = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
    title = br.title
    print(title)
    author = br.author
    year = br.year
    #author = request.args['author']
    #year = request.args['year']
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "w9Np63RHCDhV5fIkdoF43w", "isbns": isbn})
    if res.status_code != 200:
        return ('error: api request unsuccessful')
    data = res.json()
        # data["books"]["average_rating"] returned a key error.. return to this later try data[0]["average_rating"]
    ret = data["books"]
    avg = ret[0]["average_rating"]
    cnt = ret[0]["work_ratings_count"]
    cr = db.execute("SELECT rev_user FROM reviews WHERE isbn = :isbn ORDER BY rev_num DESC LIMIT 3", {"isbn": isbn})
# Checks for exisiting reviews
    if cr.rowcount == 0:
        flash("no reviews for this book, be the first to review it!")
        stuff(isbn)
    elif cr.rowcount == 1:
        ur = cr.fetchall()
        rows = cr.rowcount
        user1 = ', '.join(ur[0])
        cd = db.execute("SELECT rev_user, review, stars FROM reviews WHERE isbn = :isbn AND rev_user = :user1", {"user1": user1, "isbn": isbn}).fetchone()
        #cb = None
# Review function defined initially
        stuff(isbn)
        return render_template('book.html', stars=cd.stars, user1r=cd.review, user1=cd.rev_user, title=title, year=year, author=author, isbn=isbn, avg=avg, cnt=cnt)


    elif cr.rowcount > 0:
        ur = cr.fetchall()
        rows = cr.rowcount
        user1 = ', '.join(ur[0])
        user2 = ', '.join(ur[1])
        cd = db.execute("SELECT rev_user, review, stars FROM reviews WHERE isbn = :isbn AND rev_user = :user1", {"user1": user1, "isbn": isbn}).fetchone()
        cb = db.execute("SELECT rev_user, review, stars FROM reviews WHERE isbn = :isbn AND rev_user = :user2", {"user2": user2, "isbn": isbn}).fetchone()
        stuff(isbn)
        return render_template('book.html', stars=cd.stars, user2=cb.rev_user, stars2=cb.stars, user2r=cb.review, user1r=cd.review, user1=cd.rev_user, title=title, year=year, author=author, isbn=isbn, avg=avg, cnt=cnt)
    return render_template('book.html', title=title, year=year, author=author, isbn=isbn, avg=avg, cnt=cnt)
# Route to return from bookpage
@app.route('/back')
def back():
    print("username" in session)
    return redirect(url_for("home", username=session['username']))

@app.route('/api/<isbn>')
def isbn(isbn):
        isbn_full = request.args.get(isbn)
        red = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "w9Np63RHCDhV5fIkdoF43w", "isbns": isbn})
        if red.status_code != 200:
            return ('error: api request unsuccessful')
        data = red.json()
        rev = data["books"]
        res = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
        if res == None:
            return ("Error 404: isbn not found")
        return jsonify ({
            "title": res.title,
            "author": res.author,
            "year": res.year,
            "isbn": res.isbn,
            "review_count": rev[0]["reviews_count"],
            "average_score": rev[0]["average_rating"]
        })
