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
@app.route("/api/transactions", methods=["POST"])
def add_transaction():

    data = request.get_json()

    transaction_type = data.get("type")
    amount = data.get("amount")
    category = data.get("category")
    description = data.get("description", "")
    date = data.get("date")

    if not transaction_type or not amount or not date:
        return jsonify({
            "success": False,
            "message": "Missing required fields"
        }), 400

    if not category:
        category = categorize_transaction(description)

    connection = get_db_connection()

    connection.execute("""
        INSERT INTO transactions
        (type, amount, category, description, date)
        VALUES (?, ?, ?, ?, ?)
    """, (
        transaction_type,
        float(amount),
        category,
        description,
        date
    ))

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "message": "Transaction added successfully"
    })


@app.route("/api/transactions", methods=["GET"])
def get_transactions():

    connection = get_db_connection()

    transactions = connection.execute("""
        SELECT *
        FROM transactions
        ORDER BY date DESC, id DESC
    """).fetchall()

    connection.close()

    return jsonify([
        dict(transaction)
        for transaction in transactions
    ])


@app.route("/api/transactions/<int:transaction_id>",
           methods=["PUT"])
def update_transaction(transaction_id):

    data = request.get_json()

    connection = get_db_connection()

    cursor = connection.execute("""
        UPDATE transactions
        SET
            type = ?,
            amount = ?,
            category = ?,
            description = ?,
            date = ?
        WHERE id = ?
    """, (
        data.get("type"),
        float(data.get("amount")),
        data.get("category"),
        data.get("description", ""),
        data.get("date"),
        transaction_id
    ))

    connection.commit()
    connection.close()

    if cursor.rowcount == 0:
        return jsonify({
            "success": False,
            "message": "Transaction not found"
        }), 404

    return jsonify({
        "success": True,
        "message": "Transaction updated"
    })


@app.route("/api/transactions/<int:transaction_id>",
           methods=["DELETE"])
def delete_transaction(transaction_id):

    connection = get_db_connection()

    cursor = connection.execute("""
        DELETE FROM transactions
        WHERE id = ?
    """, (transaction_id,))

    connection.commit()
    connection.close()

    if cursor.rowcount == 0:
        return jsonify({
            "success": False,
            "message": "Transaction not found"
        }), 404

    return jsonify({
        "success": True,
        "message": "Transaction deleted"
    })


@app.route("/api/categorize", methods=["POST"])
def categorize():

    data = request.get_json()

    description = data.get("description", "")

    category = categorize_transaction(description)

    return jsonify({
        "description": description,
        "category": category
    })

@app.route("/api/summary")
def get_summary():

    return jsonify(
        calculate_financial_summary()
    )


@app.route("/api/dashboard")
def dashboard():

    summary = calculate_financial_summary()

    connection = get_db_connection()

    recent_transactions = connection.execute("""
        SELECT *
        FROM transactions
        ORDER BY date DESC, id DESC
        LIMIT 5
    """).fetchall()

    connection.close()

    return jsonify({
        "summary": summary,
        "recent_transactions": [
            dict(transaction)
            for transaction in recent_transactions
        ],
        "insights": generate_insights(),
        "health": calculate_financial_health()
    })

@app.route("/api/spending-by-category")
def spending_by_category():

    connection = get_db_connection()

    results = connection.execute("""
        SELECT category, SUM(amount) AS total
        FROM transactions
        WHERE type = 'expense'
        GROUP BY category
        ORDER BY total DESC
    """).fetchall()

    connection.close()

    return jsonify([
        {
            "category": row["category"],
            "total": round(row["total"], 2)
        }
        for row in results
    ])


@app.route("/api/monthly-summary")
def monthly_summary():

    connection = get_db_connection()

    results = connection.execute("""
        SELECT
            substr(date, 1, 7) AS month,

            SUM(
                CASE
                    WHEN type = 'income'
                    THEN amount
                    ELSE 0
                END
            ) AS income,

            SUM(
                CASE
                    WHEN type = 'expense'
                    THEN amount
                    ELSE 0
                END
            ) AS expenses

        FROM transactions

        GROUP BY substr(date, 1, 7)

        ORDER BY month
    """).fetchall()

    connection.close()

    return jsonify([
        {
            "month": row["month"],
            "income": round(row["income"], 2),
            "expenses": round(row["expenses"], 2)
        }
        for row in results
    ])


@app.route("/api/budgets", methods=["POST"])
def add_budget():

    data = request.get_json()

    category = data.get("category")
    amount = data.get("amount")

    if not category or amount is None:
        return jsonify({
            "success": False,
            "message": "Category and amount are required"
        }), 400

    connection = get_db_connection()

    connection.execute("""
        INSERT INTO budgets
        (category, amount)
        VALUES (?, ?)

        ON CONFLICT(category)
        DO UPDATE SET amount = excluded.amount
    """, (
        category,
        float(amount)
    ))

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "message": "Budget saved"
    })


@app.route("/api/budgets")
def get_budgets():

    connection = get_db_connection()

    budgets = connection.execute("""
        SELECT *
        FROM budgets
        ORDER BY category
    """).fetchall()

    connection.close()

    return jsonify([
        dict(budget)
        for budget in budgets
    ])


@app.route("/api/budget-progress")
def budget_progress():

    connection = get_db_connection()

    budgets = connection.execute("""
        SELECT category, amount
        FROM budgets
    """).fetchall()

    result = []

    for budget in budgets:

        spending = connection.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE type = 'expense'
            AND category = ?
        """, (
            budget["category"],
        )).fetchone()[0]

        budget_amount = budget["amount"]

        if budget_amount > 0:
            percentage = (
                spending / budget_amount
            ) * 100
        else:
            percentage = 0

        result.append({
            "category": budget["category"],
            "budget": round(budget_amount, 2),
            "spent": round(spending, 2),
            "percentage": round(percentage, 2),
            "remaining": round(
                budget_amount - spending,
                2
            )
        })

    connection.close()

    return jsonify(result)





if __name__ == "__main__":

    init_database()

    app.run(debug=True)