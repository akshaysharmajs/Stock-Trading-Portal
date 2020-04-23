import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

import random, threading, webbrowser

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
    rows = db.execute("SELECT * from portfolio WHERE userid = :id", id=session["user_id"])
    cash = db.execute("SELECT cash from users WHERE id = :id", id=session["user_id"])
    total = cash[0]["cash"]
    for i in range(len(rows)):
        total = total + rows[i]['total']
    """Show portfolio of stocks"""
    return render_template("index.html", rows=rows, cash=round(cash[0]["cash"]), total=round(total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("please provide a symbol", 400)

        if not lookup(request.form.get("symbol")):
            return apology("invalid symbol", 400)
        
        if not request.form.get("shares"):
            return apology("missing shares", 400)
            
        elif not request.form.get("shares").isdigit():
            return apology("invalid shares", 400)
        
        elif type(request.form.get("shares")) == int:
            if request.form.get("shares") <= 0:
                return apology("invalid shares", 400)
        
        shareinfo = lookup(request.form.get("symbol"))

        usercash = db.execute("SELECT cash from users WHERE id= :id", id=session["user_id"])

        alreadyexist = db.execute("SELECT * from portfolio WHERE userid=:id and  comname=:comname",
                                  id=session["user_id"], comname=shareinfo["name"])

        if usercash[0]["cash"] < (shareinfo["price"] * float(request.form.get("shares"))):
            return apology("can't afford")

        usercash[0]["cash"] = usercash[0]["cash"] - (shareinfo["price"] * float(request.form.get("shares")))

        db.execute("UPDATE users SET cash = :cash WHERE id = :id ", cash=round(usercash[0]["cash"]), id=session["user_id"])
        if len(alreadyexist) == 0:
            db.execute("INSERT INTO portfolio  VALUES (':id',:symbol,:comname,:shares,':price',':total')",
                       id=session["user_id"], symbol=shareinfo["symbol"], comname=shareinfo["name"], shares=request.form.get("shares"), price=round(shareinfo["price"]), total=round((shareinfo["price"] * float(request.form.get("shares")))))
        if len(alreadyexist) == 1:
            db.execute("UPDATE portfolio SET shares = shares + :shares, total = total + :total WHERE userid=:id and comname=:comname",
                       shares=request.form.get("shares"), total=round((shareinfo["price"] * float(request.form.get("shares")))), id=session["user_id"], comname=shareinfo["name"])

        db.execute("INSERT INTO history VALUES (':id',:symbol,:shares,':price', CURRENT_TIMESTAMP)",
                   id=session["user_id"], symbol=shareinfo["symbol"], shares=request.form.get("shares"), price=round(shareinfo["price"]))
        return redirect("/")
        # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/check", methods=["GET"])
def check():
    username = request.args.get("username")
    if len(username) <= 1:
        return jsonify(False)
    rows = db.execute("SELECT * from users WHERE username = :username", username=username)
    if len(rows) == 0:
        return jsonify(True)
    else:
        return jsonify(False)
        

@app.route("/history")
@login_required
def history():
    rows = db.execute("SELECT * from history WHERE userid = :id ORDER BY transacted ", id=session["user_id"])
    """Show history of transactions"""
    return render_template("history.html", rows=rows)


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
      # User reached route via POST (as by submitting a form via POST)

    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("please provide a symbol", 400)

        if not lookup(request.form.get("symbol")):
            return apology("invalid symbol", 400)

        shareinfo = lookup(request.form.get("symbol"))
        return render_template("quoted.html", name=shareinfo["name"], symbol=shareinfo["symbol"], price=round(shareinfo["price"]))
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")
    """Get stock quote."""


@app.route("/register", methods=["GET"])
def get_register():
    return render_template("register.html")
    

@app.route("/register", methods=["POST"])
def register():

    name = request.form.get("username")

    password = request.form.get("password")

    confirm = request.form.get("confirmation")

    rows = db.execute("SELECT * FROM users WHERE username = :username", username=name)
    x = list(db.execute("SELECT username from users"))
    idnumber = len(x)
    # Ensure username was submitted
    if not request.form.get("username"):
        return apology("must provide username", 400)

    elif len(rows) != 0:
        return apology("username already exist", 400)

    # Ensure password was submitted
    elif not request.form.get("password"):
        return apology("must provide password", 400)

    elif password != confirm:
        return apology("confirmation password doesn't match", 400)

    idnumber = idnumber + 1
    db.execute("INSERT INTO users VALUES (':id',:username,:hash,'10000')", 
               id=idnumber, username=name, hash=generate_password_hash(password))
    return redirect("/")
    
    
"""Register user"""


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("symbol missing", 403)

        elif not lookup(request.form.get("symbol")):
            return apology("invalid symbol", 403)

        if not request.form.get("shares"):
            return apology("missing shares", 403)

        shareinfo = lookup(request.form.get("symbol"))

        usercash = db.execute("SELECT cash from users WHERE id= :id", id=session["user_id"])

        sharesavail = db.execute("SELECT shares from portfolio WHERE userid = :id and symbol = :symbol", 
                                 id=session["user_id"], symbol=shareinfo["symbol"])

        if sharesavail[0]['shares'] < int(request.form.get("shares")):
            return apology("too many shares")

        elif sharesavail[0]['shares'] == int(request.form.get("shares")):
            db.execute("DELETE from portfolio WHERE userid = :id and symbol = :symbol", 
                       id=session["user_id"], symbol=shareinfo["symbol"])

        elif sharesavail[0]['shares'] > int(request.form.get("shares")):
            db.execute("UPDATE portfolio SET total = total - :total, shares=shares-:shares WHERE userid = :id and symbol=:symbol",
                       total=round((shareinfo["price"] * float(request.form.get("shares")))), shares=request.form.get("shares"), id=session["user_id"], symbol=shareinfo["symbol"])

        db.execute("UPDATE users SET cash = cash + :cash WHERE id= :id ", 
                   id=session["user_id"], cash=round((shareinfo["price"] * float(request.form.get("shares")))))
        db.execute("INSERT INTO history VALUES (':id',:symbol,-:shares,':price', CURRENT_TIMESTAMP)",
                   id=session["user_id"], symbol=shareinfo["symbol"], shares=request.form.get("shares"), price=round(shareinfo["price"]))
        return redirect("/")

    else:
        symbols = db.execute("SELECT symbol from portfolio WHERE userid=:id", id=session["user_id"])
        return render_template("sell.html", symbols=symbols)
        

@app.route("/Addcash", methods=["GET", "POST"])
@login_required
def addcash():
      # User reached route via POST (as by submitting a form via POST)

    if request.method == "POST":

        if not request.form.get("addcash"):
            return apology("missing amount", 400)

        db.execute("UPDATE users SET cash = cash + :cash WHERE id = :id ",
                   cash=round(request.form.get("addcash")), id=session["user_id"])
        return redirect("/")
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("addcash.html")
    """Get stock quote."""
    

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)

def main():
    url = "http://127.0.0.1:5000"

    threading.Timer(1.25, lambda: webbrowser.open(url) ).start()

    app.run(port=5000, debug=False)

# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


if __name__ == '__main__':
        main()
