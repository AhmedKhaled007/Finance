import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows = db.execute("select sum(shares),symbol from orders where userID = :userid GROUP BY symbol", userid = session["user_id"])
    info = []
    totalstock = 0
    for i,row in enumerate(rows):
        if row["sum(shares)"] == 0:
            continue
        info.append(lookup(row["symbol"]))

        info[i]["shares"] = row["sum(shares)"]
        info[i]["total"] = usd(info[i]["price"] * info[i]["shares"])
        totalstock += info[i]["price"] * info[i]["shares"]
        info[i]["price"] = usd(info[i]["price"])
    rows = db.execute("SELECT cash FROM users WHERE id = :uid",uid = session["user_id"])
    cash = rows[0]["cash"]
    return render_template("index.html", rows = info, cash = usd(cash), total = usd(cash+totalstock))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST" :
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        if not symbol:
            return apology("missing symbol", 400)
        if not lookup(symbol) :
            return apology("invalid symbol", 400)
        if shares  < 1:
            return apology("invalid number", 400)
        info = lookup(symbol)
        rows = db.execute("SELECT cash FROM users WHERE id = :uid",
                         uid = session["user_id"])
        cash = rows[0]["cash"]

        if info["price"] * shares < cash:
            a = db.execute("insert into orders (symbol,price,userID,shares) values (:symbol, :price, :userID, :shares)",
                          symbol = symbol.upper(), price = info["price"], userID = session["user_id"], shares = shares)

            b = db.execute("update users set cash = :cash where id = :uid",
                          cash = cash - info["price"] * shares ,uid = session["user_id"])
            return redirect("/")
        else:
            return apology("can't afford", 409)

    else:
        return render_template("buy.html")


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    username = request.args.get("username")
    rows = db.execute("SELECT * FROM users WHERE username = :username",username=username)
    if  len(username) > 0 and len(rows) == 0:
        return jsonify(True)
    else:
        return jsonify(False)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("select * from orders where userID = :userid", userid = session["user_id"])
    return render_template("history.html", rows = rows)



@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST" :
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("missing symbol", 400)
        if not lookup(symbol) :
            return apology("invalid symbol", 400)
        else :
            info = lookup(symbol)
            return render_template("quoted.html", name = info["name"], symbol = info["symbol"], price = info["price"])
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

    # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)
    # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        elif  request.form.get("password") != request.form.get("confirmation"):
            return apology("must confirm password", 400)
        rows = db.execute("SELECT * FROM users WHERE username = :username",
            username=request.form.get("username"))
        if len(rows) == 1 :
            return apology("user name already exist", 400)
        else:
            hashpass = generate_password_hash(request.form.get("password"))
            a = db.execute("insert into users (username,hash) values (:username, :hash1)", username = request.form.get("username"), hash1 = hashpass)
            return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        shares = int(request.form.get("shares"))
        symbol = request.form.get("symbol")
        info = lookup(symbol)
        rows = db.execute("SELECT cash FROM users WHERE id = :uid",
                         uid = session["user_id"])
        cash = rows[0]["cash"]
        rows = db.execute("select sum(shares) from orders where userID = :userid GROUP BY symbol Having symbol = :symbol", userid = session["user_id"] , symbol = symbol)
        if shares > rows[0]["sum(shares)"]:
            return apology("Too many shars",400)
        else :

            a = db.execute("insert into orders (symbol,price,userID,shares) values (:symbol, :price, :userID, :shares)",
                          symbol = symbol, price = info["price"], userID = session["user_id"], shares = -shares)

            b = db.execute("update users set cash = :cash where id = :uid",
                          cash = cash + info["price"] * shares ,uid = session["user_id"])
        return redirect("/")
    else :
        rows = db.execute("SELECT DISTINCT symbol FROM orders WHERE userID = :uid",uid = session["user_id"])
        return render_template("sell.html",rows = rows)



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)