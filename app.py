import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    if request.method == "GET":
        id = session["user_id"]
        stocks = db.execute("SELECT * FROM stocks WHERE user_id LIKE ?", id)
        rows = db.execute("SELECT cash FROM users WHERE id = ?", id)
        cash = rows[0]["cash"] if rows else 0
        grand_total = cash

        for stock in stocks:
            symbol = stock["symbol"]
            price = lookup(symbol)["price"]
            shares = stock["shares"]
            total = float(price * shares)
            grand_total = float(grand_total) + float(total)
            stock["price"] = price
            stock["total"] = total
        stock_holdings = grand_total - cash
        return render_template("index.html", stocks=stocks, cash=cash, grand_total=grand_total, stock_holdings=stock_holdings)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    user_id = session["user_id"]
    rows = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    cash = rows[0]["cash"] if rows else 0
    if request.method == 'GET':
        return render_template("buy.html", cash=cash)
    elif request.method == 'POST':
        purchase = request.form['symbol']
        shares = request.form['shares']
        if not shares.isdigit():
            return apology("enter valid shares")
        data = lookup(purchase)
        if data is not None:
            if (int(shares) > 0):
                total_cost = (data["price"] * int(shares))
                if float(total_cost) <= cash:
                    id = session["user_id"]
                    db.execute("UPDATE users SET cash = ? WHERE id LIKE ?", (cash - float(total_cost)), id)
                    existing_stock = db.execute("SELECT * FROM stocks WHERE user_id = ? AND symbol = ?", id, purchase)
                    if existing_stock:
                        new_shares = existing_stock[0]['shares'] + int(shares)
                        db.execute("UPDATE stocks SET shares = ? WHERE user_id = ? AND symbol = ?", new_shares, id, purchase)
                        db.execute("INSERT INTO history (user_id, stock, amount_of_shares, price_per_share, total, transaction_type, date_of_transaction, time_of_transaction) VALUES (?, ?, ?, ?, ?, 'BUY', DATE('now'), TIME('now','+3 hours'))", id, purchase, shares, usd(data["price"]), usd(total_cost))
                    else:
                        db.execute("INSERT INTO stocks (user_id, symbol, shares) VALUES (?, ?, ?)", id, purchase, shares)
                        db.execute("INSERT INTO history (user_id, stock, amount_of_shares, price_per_share, total, transaction_type, date_of_transaction, time_of_transaction) VALUES (?, ?, ?, ?, ?, 'BUY', DATE('now'), TIME('now','+3 hours'))", id, purchase, shares, usd(data["price"]), usd(total_cost))
                    return redirect("/")
                else:
                    return apology("Insufficient funds")
            else:
                return apology("Invalid number of shares")
        else:
            return apology("Invalid stock symbol")

@app.route("/purchase_successful", methods=["GET", "POST"])
@login_required
def purchase_successful():
    if request.method == "GET":
        return render_template("purchase_successful.html")
    else:
        return redirect("/buy")
@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    if request.method == 'GET':
        id = session["user_id"]
        data = db.execute("SELECT * FROM history WHERE user_id LIKE ?", id)
        return render_template("history.html", data=data)
    return apology("TODO")


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

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
    if request.method == 'GET':
        return render_template("quote.html")
    if request.method == 'POST':
        stock = request.form['symbol']
        if (lookup(stock) != None):
            data = lookup(stock)
            price = data["price"]
            return render_template("quote.html", data=data, price=usd(price))
        else:
            return apology("Invalid Stock")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == 'GET':
        return render_template("register.html")
    elif request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if (request.form['password'] == request.form['confirmation'] and username != '' and len(password) >= 6):
            result = db.execute("SELECT * FROM users WHERE username LIKE ?", username)
            if not result:
                db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, generate_password_hash(password))
                return redirect("/login")
            else:
                return apology("Username is taken")
        elif (len(password) < 6):
            return apology("Password is too short")
        elif (username == ''):
            return apology("Invalid Username")
        elif (password != request.form['confirmation']):
            return apology("Passwords do not match")
        else:
            return apology("Please enter valid data")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    id = session["user_id"]
    rows = db.execute("SELECT cash FROM users WHERE id = ?", id)
    cash = rows[0]["cash"] if rows else 0
    if request.method == "GET":
        stocks = db.execute("SELECT * FROM stocks WHERE user_id LIKE ?", id)

        for stock in stocks:
            symbol = stock["symbol"]
            price = lookup(symbol)["price"]
            shares = stock["shares"]
            stock["price"] = usd(price)
            stock["total"] = price * shares
        return render_template("sell.html", stocks=stocks, cash=usd(cash))
    elif request.method == "POST":
        selected_stock = request.form['symbol']
        amount_to_sell = request.form['shares']
        id = session["user_id"]
        result = db.execute("SELECT shares FROM stocks WHERE user_id LIKE ? AND symbol LIKE ?", id, selected_stock)
        if not result:
            return apology("Stock not found or user does not own any shares of this stock")
        shares = result[0]['shares']
        if (int(amount_to_sell) > shares):
            return apology("Cant sell more shares than you own")
        total = lookup(selected_stock)["price"] * float(amount_to_sell)
        sum = cash + total
        user_shares = int(result[0]["shares"])
        db.execute("INSERT INTO history (user_id, stock, amount_of_shares, price_per_share, total, transaction_type, date_of_transaction, time_of_transaction) VALUES (?, ?, ?, ?, ?, 'SELL', DATE('now'), TIME('now','+3 hours'))", id, selected_stock, amount_to_sell, usd(lookup(selected_stock)["price"]), usd(total))
        db.execute("UPDATE stocks SET shares = ? WHERE user_id LIKE ? AND symbol LIKE ?",(user_shares - int(amount_to_sell)), id, selected_stock)
        db.execute("UPDATE users SET cash = ? WHERE id LIKE ?", sum, id)
        return redirect("/")