from flask import Flask, render_template, jsonify, request
import sqlite3
import pandas as pd
import os

app = Flask(__name__)

DATABASE = "finance.db"
UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_database():

    connection = get_db_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            date TEXT NOT NULL
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL UNIQUE,
            amount REAL NOT NULL
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            target REAL NOT NULL,
            current REAL DEFAULT 0,
            deadline TEXT
        )
    """)

    connection.commit()
    connection.close()

CATEGORY_KEYWORDS = {

    "Food": [
        "zomato",
        "swiggy",
        "restaurant",
        "pizza",
        "food"
    ],

    "Transport": [
        "uber",
        "ola",
        "petrol",
        "bus",
        "metro"
    ],

    "Shopping": [
        "amazon",
        "flipkart",
        "myntra"
    ],

    "Bills": [
        "jio",
        "airtel",
        "electricity",
        "recharge"
    ],

    "Entertainment": [
        "netflix",
        "spotify",
        "movie"
    ],

    "Health": [
        "hospital",
        "pharmacy",
        "medical",
        "medicine"
    ],

    "Education": [
        "college",
        "course",
        "book",
        "education"
    ]
}


def categorize_transaction(description):

    description = description.lower()

    for category, keywords in CATEGORY_KEYWORDS.items():

        for keyword in keywords:

            if keyword in description:
                return category

    return "Other"


def calculate_financial_summary():

    connection = get_db_connection()

    income_result = connection.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM transactions
        WHERE type = 'income'
    """).fetchone()

    expense_result = connection.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM transactions
        WHERE type = 'expense'
    """).fetchone()

    connection.close()

    total_income = income_result[0]
    total_expenses = expense_result[0]

    balance = total_income - total_expenses

    if total_income > 0:
        savings_rate = (
            balance / total_income
        ) * 100
    else:
        savings_rate = 0

    return {
        "income": round(total_income, 2),
        "expenses": round(total_expenses, 2),
        "balance": round(balance, 2),
        "savings_rate": round(savings_rate, 2)
    }


def generate_insights():

    insights = []

    connection = get_db_connection()

    budgets = connection.execute("""
        SELECT category, amount
        FROM budgets
    """).fetchall()

    for budget in budgets:

        spent = connection.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE type = 'expense'
            AND category = ?
        """, (budget["category"],)).fetchone()[0]

        budget_amount = budget["amount"]

        if budget_amount <= 0:
            continue

        percentage = (
            spent / budget_amount
        ) * 100

        if percentage > 100:

            insights.append({
                "type": "danger",
                "title": "Budget Exceeded",
                "message":
                    f"You exceeded your "
                    f"{budget['category']} budget by "
                    f"₹{spent - budget_amount:.2f}."
            })

        elif percentage >= 80:

            insights.append({
                "type": "warning",
                "title": "Budget Alert",
                "message":
                    f"You have used "
                    f"{percentage:.0f}% of your "
                    f"{budget['category']} budget."
            })

    connection.close()

    summary = calculate_financial_summary()

    if summary["income"] > 0:

        if summary["savings_rate"] < 20:

            insights.append({
                "type": "warning",
                "title": "Savings Opportunity",
                "message":
                    "Your current savings rate is below 20%."
            })

        elif summary["savings_rate"] >= 30:

            insights.append({
                "type": "positive",
                "title": "Strong Savings",
                "message":
                    f"You're currently saving "
                    f"{summary['savings_rate']:.1f}% "
                    f"of your income."
            })

    return insights


def calculate_financial_health():

    summary = calculate_financial_summary()

    score = 50

    if summary["savings_rate"] >= 30:
        score += 20

    elif summary["savings_rate"] >= 20:
        score += 10

    elif summary["savings_rate"] < 10:
        score -= 10

    if summary["balance"] < 0:
        score -= 20

    score = max(0, min(score, 100))

    if score >= 75:
        status = "Good Health"

    elif score >= 50:
        status = "Moderate Health"

    else:
        status = "Needs Attention"

    return {
        "score": score,
        "status": status
    }


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/test")
def api_test():

    return jsonify({
        "message": "FinFlow backend connected",
        "status": "success"
    })




if __name__ == "__main__":

    init_database()

    app.run(debug=True)