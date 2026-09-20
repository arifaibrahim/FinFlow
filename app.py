from flask import Flask, render_template, jsonify, request
import sqlite3
import pandas as pd
import os
from datetime import datetime, date

# =========================================================
# FINFLOW — MONEY IN MOTION
# Backend
# =========================================================

app = Flask(__name__)

DATABASE = "finance.db"
UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# =========================================================
# DATABASE
# =========================================================

def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_database():

    connection = get_db_connection()

    # -----------------------------
    # Transactions
    # -----------------------------

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

    # -----------------------------
    # Budgets
    # -----------------------------

    connection.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL UNIQUE,
            amount REAL NOT NULL
        )
    """)

    # -----------------------------
    # Goals
    # -----------------------------

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


# =========================================================
# CONSTANTS
# =========================================================

CATEGORIES = [
    "Food",
    "Transport",
    "Shopping",
    "Education",
    "Bills",
    "Entertainment",
    "Health",
    "Salary",
    "Other"
]


CATEGORY_KEYWORDS = {

    "Food": [
        "zomato",
        "swiggy",
        "restaurant",
        "food",
        "pizza",
        "cafe",
        "coffee",
        "hotel",
        "bakery",
        "grocery",
        "groceries"
    ],

    "Transport": [
        "uber",
        "ola",
        "petrol",
        "fuel",
        "bus",
        "metro",
        "taxi",
        "rapido",
        "transport",
        "parking"
    ],

    "Shopping": [
        "amazon",
        "flipkart",
        "myntra",
        "shopping",
        "mall",
        "store",
        "retail"
    ],

    "Bills": [
        "jio",
        "airtel",
        "vi",
        "vodafone",
        "electricity",
        "recharge",
        "internet",
        "wifi",
        "bill",
        "utility",
        "water"
    ],

    "Entertainment": [
        "netflix",
        "spotify",
        "movie",
        "cinema",
        "youtube",
        "prime",
        "entertainment",
        "game"
    ],

    "Health": [
        "hospital",
        "pharmacy",
        "medical",
        "medicine",
        "doctor",
        "clinic",
        "health"
    ],

    "Education": [
        "college",
        "course",
        "book",
        "education",
        "school",
        "university",
        "tuition",
        "exam"
    ],

    "Salary": [
        "salary",
        "payroll",
        "stipend",
        "wages",
        "income"
    ]
}


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def normalize_transaction_type(transaction_type):

    if transaction_type is None:
        return None

    value = str(transaction_type).strip().lower()

    if value in [
        "income",
        "credit",
        "credited",
        "deposit",
        "salary"
    ]:
        return "income"

    if value in [
        "expense",
        "debit",
        "debited",
        "withdrawal",
        "payment"
    ]:
        return "expense"

    return None


def normalize_date(value):

    if value is None:
        return None

    try:
        parsed = pd.to_datetime(value)
        return parsed.strftime("%Y-%m-%d")

    except Exception:
        return None


def categorize_transaction(description):

    if not description:
        return "Other"

    description = str(description).lower()

    for category, keywords in CATEGORY_KEYWORDS.items():

        for keyword in keywords:

            if keyword in description:
                return category

    return "Other"


def get_requested_year():

    value = request.args.get("year")

    if value:

        try:
            return int(value)
        except ValueError:
            pass

    return datetime.now().year


def get_requested_month():

    value = request.args.get("month")

    if value and value != "all":

        try:
            month = int(value)

            if 1 <= month <= 12:
                return month

        except ValueError:
            pass

    return None


def month_name(month_number):

    names = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December"
    ]

    return names[month_number - 1]


def calculate_percentage_change(current, previous):

    current = float(current or 0)
    previous = float(previous or 0)

    if previous == 0:

        if current == 0:
            return 0

        return None

    return round(
        ((current - previous) / abs(previous)) * 100,
        2
    )


def get_month_summary(year, month):

    connection = get_db_connection()

    start_date = f"{year}-{month:02d}-01"

    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1

    end_date = f"{next_year}-{next_month:02d}-01"

    result = connection.execute("""
        SELECT
            COALESCE(
                SUM(
                    CASE
                        WHEN type = 'income'
                        THEN amount
                        ELSE 0
                    END
                ),
                0
            ) AS income,

            COALESCE(
                SUM(
                    CASE
                        WHEN type = 'expense'
                        THEN amount
                        ELSE 0
                    END
                ),
                0
            ) AS expenses

        FROM transactions

        WHERE date >= ?
        AND date < ?
    """, (
        start_date,
        end_date
    )).fetchone()

    connection.close()

    income = float(result["income"] or 0)
    expenses = float(result["expenses"] or 0)

    balance = income - expenses

    savings_rate = (
        (balance / income) * 100
        if income > 0
        else 0
    )

    return {
        "income": round(income, 2),
        "expenses": round(expenses, 2),
        "balance": round(balance, 2),
        "savings_rate": round(savings_rate, 2)
    }


def get_previous_month(year, month):

    if month == 1:
        return year - 1, 12

    return year, month - 1


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

    total_income = float(income_result[0] or 0)
    total_expenses = float(expense_result[0] or 0)

    balance = total_income - total_expenses

    if total_income > 0:

        savings_rate = (
            balance / total_income
        ) * 100

    else:
        savings_rate = 0

    # Current month
    now = datetime.now()

    current_year = now.year
    current_month = now.month

    current = get_month_summary(
        current_year,
        current_month
    )

    previous_year, previous_month = get_previous_month(
        current_year,
        current_month
    )

    previous = get_month_summary(
        previous_year,
        previous_month
    )

    balance_change = calculate_percentage_change(
        current["balance"],
        previous["balance"]
    )

    income_change = calculate_percentage_change(
        current["income"],
        previous["income"]
    )

    expense_change = calculate_percentage_change(
        current["expenses"],
        previous["expenses"]
    )

    savings_change = calculate_percentage_change(
        current["savings_rate"],
        previous["savings_rate"]
    )

    return {

        "income": round(total_income, 2),

        "expenses": round(total_expenses, 2),

        "balance": round(balance, 2),

        "savings_rate": round(savings_rate, 2),

        "current_month": current_month,

        "current_year": current_year,

        "changes": {

            "balance": balance_change,

            "income": income_change,

            "expenses": expense_change,

            "savings_rate": savings_change
        }
    }


# =========================================================
# SMART COACH
# =========================================================

def generate_insights():

    insights = []

    connection = get_db_connection()

    # -----------------------------
    # Budget insights
    # -----------------------------

    budgets = connection.execute("""
        SELECT category, amount
        FROM budgets
        ORDER BY category
    """).fetchall()

    now = datetime.now()

    year = now.year
    month = now.month

    start_date = f"{year}-{month:02d}-01"

    if month == 12:
        next_date = f"{year + 1}-01-01"
    else:
        next_date = f"{year}-{month + 1:02d}-01"

    for budget in budgets:

        spent = connection.execute("""
            SELECT COALESCE(SUM(amount), 0)

            FROM transactions

            WHERE type = 'expense'

            AND category = ?

            AND date >= ?

            AND date < ?
        """, (
            budget["category"],
            start_date,
            next_date
        )).fetchone()[0]

        budget_amount = float(
            budget["amount"]
        )

        spent = float(spent or 0)

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

    # -----------------------------
    # Savings insight
    # -----------------------------

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

    # -----------------------------
    # Spending insight
    # -----------------------------

    connection = get_db_connection()

    largest_category = connection.execute("""
        SELECT
            category,
            SUM(amount) AS total

        FROM transactions

        WHERE type = 'expense'

        GROUP BY category

        ORDER BY total DESC

        LIMIT 1
    """).fetchone()

    connection.close()

    if largest_category:

        insights.append({
            "type": "info",
            "title": "Spending Insight",
            "message":
                f"Your highest spending category is "
                f"{largest_category['category']} "
                f"at ₹{largest_category['total']:.2f}."
        })

    if not insights:

        insights.append({
            "type": "info",
            "title": "Getting Started",
            "message":
                "Add transactions and budgets to receive "
                "personalized financial insights."
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

    score = max(
        0,
        min(score, 100)
    )

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


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template("index.html")


@app.route("/api/test")
def api_test():

    return jsonify({
        "message": "FinFlow backend connected",
        "status": "success"
    })


# =========================================================
# TRANSACTIONS
# =========================================================

@app.route(
    "/api/transactions",
    methods=["POST"]
)
def add_transaction():

    data = request.get_json() or {}

    transaction_type = normalize_transaction_type(
        data.get("type")
    )

    amount = data.get("amount")

    category = data.get("category")

    description = data.get(
        "description",
        ""
    )

    transaction_date = normalize_date(
        data.get("date")
    )

    if not transaction_type:

        return jsonify({
            "success": False,
            "message":
                "Type must be income or expense"
        }), 400

    try:

        amount = float(amount)

    except (TypeError, ValueError):

        return jsonify({
            "success": False,
            "message": "Invalid amount"
        }), 400

    if amount <= 0:

        return jsonify({
            "success": False,
            "message":
                "Amount must be greater than zero"
        }), 400

    if not transaction_date:

        return jsonify({
            "success": False,
            "message":
                "A valid date is required"
        }), 400

    if not category:

        category = categorize_transaction(
            description
        )

    if category not in CATEGORIES:

        category = "Other"

    connection = get_db_connection()

    connection.execute("""
        INSERT INTO transactions
        (
            type,
            amount,
            category,
            description,
            date
        )

        VALUES (?, ?, ?, ?, ?)
    """, (
        transaction_type,
        amount,
        category,
        description,
        transaction_date
    ))

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "message":
            "Transaction added successfully"
    })


@app.route("/api/transactions")
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


@app.route(
    "/api/transactions/<int:transaction_id>",
    methods=["PUT"]
)
def update_transaction(transaction_id):

    data = request.get_json() or {}

    transaction_type = normalize_transaction_type(
        data.get("type")
    )

    try:

        amount = float(
            data.get("amount")
        )

    except (TypeError, ValueError):

        return jsonify({
            "success": False,
            "message": "Invalid amount"
        }), 400

    category = data.get(
        "category",
        "Other"
    )

    description = data.get(
        "description",
        ""
    )

    transaction_date = normalize_date(
        data.get("date")
    )

    if not transaction_type:

        return jsonify({
            "success": False,
            "message": "Invalid transaction type"
        }), 400

    if amount <= 0:

        return jsonify({
            "success": False,
            "message": "Amount must be greater than zero"
        }), 400

    if not transaction_date:

        return jsonify({
            "success": False,
            "message": "Invalid date"
        }), 400

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
        transaction_type,
        amount,
        category,
        description,
        transaction_date,
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


@app.route(
    "/api/transactions/<int:transaction_id>",
    methods=["DELETE"]
)
def delete_transaction(transaction_id):

    connection = get_db_connection()

    cursor = connection.execute("""
        DELETE FROM transactions
        WHERE id = ?
    """, (
        transaction_id,
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
        "message": "Transaction deleted"
    })


# =========================================================
# CATEGORIZATION
# =========================================================

@app.route(
    "/api/categorize",
    methods=["POST"]
)
def categorize():

    data = request.get_json() or {}

    description = data.get(
        "description",
        ""
    )

    category = categorize_transaction(
        description
    )

    return jsonify({
        "description": description,
        "category": category
    })


@app.route("/api/categories")
def get_categories():

    return jsonify(CATEGORIES)


# =========================================================
# FINANCIAL SUMMARY
# =========================================================

@app.route("/api/summary")
def get_summary():

    return jsonify(
        calculate_financial_summary()
    )


# =========================================================
# DASHBOARD
# =========================================================

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


# =========================================================
# SPENDING BY CATEGORY
# =========================================================

@app.route("/api/spending-by-category")
def spending_by_category():

    year = get_requested_year()
    month = get_requested_month()

    connection = get_db_connection()

    if month:

        start_date = f"{year}-{month:02d}-01"

        if month == 12:

            end_date = f"{year + 1}-01-01"

        else:

            end_date = f"{year}-{month + 1:02d}-01"

        rows = connection.execute("""
            SELECT
                category,
                COALESCE(SUM(amount), 0) AS total

            FROM transactions

            WHERE type = 'expense'

            AND date >= ?

            AND date < ?

            GROUP BY category

            ORDER BY total DESC
        """, (
            start_date,
            end_date
        )).fetchall()

    else:

        rows = connection.execute("""
            SELECT
                category,
                COALESCE(SUM(amount), 0) AS total

            FROM transactions

            WHERE type = 'expense'

            AND strftime('%Y', date) = ?

            GROUP BY category

            ORDER BY total DESC
        """, (
            str(year),
        )).fetchall()

    connection.close()

    data = {
        category: 0
        for category in CATEGORIES
        if category != "Salary"
    }

    for row in rows:

        if row["category"] in data:

            data[row["category"]] = round(
                float(row["total"] or 0),
                2
            )

    return jsonify([
        {
            "category": category,
            "total": total
        }

        for category, total
        in data.items()

        if total > 0
    ])


# =========================================================
# MONTHLY SUMMARY
# =========================================================

@app.route("/api/monthly-summary")
def monthly_summary():

    year = get_requested_year()
    selected_month = get_requested_month()

    connection = get_db_connection()

    rows = connection.execute("""
        SELECT
            CAST(strftime('%m', date) AS INTEGER)
                AS month,

            COALESCE(
                SUM(
                    CASE
                        WHEN type = 'income'
                        THEN amount
                        ELSE 0
                    END
                ),
                0
            ) AS income,

            COALESCE(
                SUM(
                    CASE
                        WHEN type = 'expense'
                        THEN amount
                        ELSE 0
                    END
                ),
                0
            ) AS expenses

        FROM transactions

        WHERE strftime('%Y', date) = ?

        GROUP BY strftime('%m', date)

        ORDER BY month
    """, (
        str(year),
    )).fetchall()

    connection.close()

    monthly_data = {}

    for row in rows:

        month_number = int(
            row["month"]
        )

        monthly_data[month_number] = {
            "income": round(
                float(row["income"] or 0),
                2
            ),

            "expenses": round(
                float(row["expenses"] or 0),
                2
            )
        }

    # ---------------------------------
    # Always return all 12 months
    # ---------------------------------

    result = []

    for month_number in range(1, 13):

        values = monthly_data.get(
            month_number,
            {
                "income": 0,
                "expenses": 0
            }
        )

        result.append({

            "month": month_number,

            "month_name":
                month_name(month_number),

            "year": year,

            "income":
                values["income"],

            "expenses":
                values["expenses"]
        })

    if selected_month:

        result = [
            item
            for item in result
            if item["month"] == selected_month
        ]

    return jsonify(result)


# =========================================================
# MONTHLY COMPARISON
# =========================================================

@app.route("/api/monthly-comparison")
def monthly_comparison():

    year = get_requested_year()
    month = get_requested_month()

    if month is None:

        month = datetime.now().month

    current = get_month_summary(
        year,
        month
    )

    previous_year, previous_month = get_previous_month(
        year,
        month
    )

    previous = get_month_summary(
        previous_year,
        previous_month
    )

    return jsonify({

        "current": current,

        "previous": previous,

        "changes": {

            "income":
                calculate_percentage_change(
                    current["income"],
                    previous["income"]
                ),

            "expenses":
                calculate_percentage_change(
                    current["expenses"],
                    previous["expenses"]
                ),

            "balance":
                calculate_percentage_change(
                    current["balance"],
                    previous["balance"]
                ),

            "savings_rate":
                calculate_percentage_change(
                    current["savings_rate"],
                    previous["savings_rate"]
                )
        }
    })


# =========================================================
# BUDGETS
# =========================================================

@app.route(
    "/api/budgets",
    methods=["POST"]
)
def add_budget():

    data = request.get_json() or {}

    category = data.get("category")
    amount = data.get("amount")

    if not category:

        return jsonify({
            "success": False,
            "message": "Category is required"
        }), 400

    try:

        amount = float(amount)

    except (TypeError, ValueError):

        return jsonify({
            "success": False,
            "message": "Invalid budget amount"
        }), 400

    if amount <= 0:

        return jsonify({
            "success": False,
            "message":
                "Budget amount must be greater than zero"
        }), 400

    if category not in CATEGORIES:

        category = "Other"

    connection = get_db_connection()

    connection.execute("""
        INSERT INTO budgets
        (
            category,
            amount
        )

        VALUES (?, ?)

        ON CONFLICT(category)

        DO UPDATE SET
            amount = excluded.amount
    """, (
        category,
        amount
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


@app.route(
    "/api/budgets/<string:category>",
    methods=["DELETE"]
)
def delete_budget(category):

    connection = get_db_connection()

    cursor = connection.execute("""
        DELETE FROM budgets
        WHERE category = ?
    """, (
        category,
    ))

    connection.commit()
    connection.close()

    if cursor.rowcount == 0:

        return jsonify({
            "success": False,
            "message": "Budget not found"
        }), 404

    return jsonify({
        "success": True,
        "message": "Budget deleted"
    })


# =========================================================
# BUDGET PROGRESS
# =========================================================

@app.route("/api/budget-progress")
def budget_progress():

    year = get_requested_year()
    month = get_requested_month()

    if month is None:

        month = datetime.now().month

    connection = get_db_connection()

    budgets = connection.execute("""
        SELECT category, amount
        FROM budgets
        ORDER BY category
    """).fetchall()

    result = []

    if month == 12:

        next_year = year + 1
        next_month = 1

    else:

        next_year = year
        next_month = month + 1

    start_date = f"{year}-{month:02d}-01"
    end_date = f"{next_year}-{next_month:02d}-01"

    for budget in budgets:

        spending = connection.execute("""
            SELECT COALESCE(SUM(amount), 0)

            FROM transactions

            WHERE type = 'expense'

            AND category = ?

            AND date >= ?

            AND date < ?
        """, (
            budget["category"],
            start_date,
            end_date
        )).fetchone()[0]

        budget_amount = float(
            budget["amount"]
        )

        spending = float(
            spending or 0
        )

        if budget_amount > 0:

            percentage = (
                spending / budget_amount
            ) * 100

        else:

            percentage = 0

        result.append({

            "category":
                budget["category"],

            "budget":
                round(
                    budget_amount,
                    2
                ),

            "spent":
                round(
                    spending,
                    2
                ),

            "percentage":
                round(
                    percentage,
                    2
                ),

            "remaining":
                round(
                    budget_amount - spending,
                    2
                )
        })

    connection.close()

    return jsonify(result)


# =========================================================
# GOALS
# =========================================================

@app.route(
    "/api/goals",
    methods=["POST"]
)
def add_goal():

    data = request.get_json() or {}

    name = data.get("name")
    target = data.get("target")
    current = data.get(
        "current",
        0
    )
    deadline = data.get(
        "deadline"
    )

    if not name:

        return jsonify({
            "success": False,
            "message":
                "Goal name is required"
        }), 400

    try:

        target = float(target)
        current = float(current)

    except (TypeError, ValueError):

        return jsonify({
            "success": False,
            "message":
                "Target and current amounts must be numbers"
        }), 400

    if target <= 0:

        return jsonify({
            "success": False,
            "message":
                "Target must be greater than zero"
        }), 400

    if current < 0:

        current = 0

    if current > target:

        current = target

    if deadline:

        deadline = normalize_date(
            deadline
        )

    connection = get_db_connection()

    cursor = connection.execute("""
        INSERT INTO goals
        (
            name,
            target,
            current,
            deadline
        )

        VALUES (?, ?, ?, ?)
    """, (
        name.strip(),
        target,
        current,
        deadline
    ))

    connection.commit()

    goal_id = cursor.lastrowid

    connection.close()

    return jsonify({

        "success": True,

        "message":
            "Goal created",

        "id":
            goal_id
    })


@app.route("/api/goals")
def get_goals():

    connection = get_db_connection()

    goals = connection.execute("""
        SELECT *
        FROM goals
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    return jsonify([
        dict(goal)
        for goal in goals
    ])


@app.route(
    "/api/goals/<int:goal_id>",
    methods=["PUT"]
)
def update_goal(goal_id):

    data = request.get_json() or {}

    name = data.get("name")
    target = data.get("target")
    current = data.get("current")
    deadline = data.get("deadline")

    connection = get_db_connection()

    existing = connection.execute("""
        SELECT *
        FROM goals
        WHERE id = ?
    """, (
        goal_id,
    )).fetchone()

    if not existing:

        connection.close()

        return jsonify({
            "success": False,
            "message": "Goal not found"
        }), 404

    if name is None:
        name = existing["name"]

    if target is None:
        target = existing["target"]

    if current is None:
        current = existing["current"]

    if deadline is None:
        deadline = existing["deadline"]

    try:

        target = float(target)
        current = float(current)

    except (TypeError, ValueError):

        connection.close()

        return jsonify({
            "success": False,
            "message":
                "Invalid goal values"
        }), 400

    if target <= 0:

        connection.close()

        return jsonify({
            "success": False,
            "message":
                "Target must be greater than zero"
        }), 400

    current = max(
        0,
        min(current, target)
    )

    if deadline:

        deadline = normalize_date(
            deadline
        )

    connection.execute("""
        UPDATE goals

        SET
            name = ?,
            target = ?,
            current = ?,
            deadline = ?

        WHERE id = ?
    """, (
        name,
        target,
        current,
        deadline,
        goal_id
    ))

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "message": "Goal updated"
    })


@app.route(
    "/api/goals/<int:goal_id>",
    methods=["DELETE"]
)
def delete_goal(goal_id):

    connection = get_db_connection()

    cursor = connection.execute("""
        DELETE FROM goals
        WHERE id = ?
    """, (
        goal_id,
    ))

    connection.commit()
    connection.close()

    if cursor.rowcount == 0:

        return jsonify({
            "success": False,
            "message": "Goal not found"
        }), 404

    return jsonify({
        "success": True,
        "message": "Goal deleted"
    })


# =========================================================
# GOAL PROGRESS
# =========================================================

@app.route("/api/goal-progress")
def goal_progress():

    connection = get_db_connection()

    goals = connection.execute("""
        SELECT *
        FROM goals
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    result = []

    for goal in goals:

        target = float(
            goal["target"]
        )

        current = float(
            goal["current"]
        )

        if target > 0:

            percentage = (
                current / target
            ) * 100

        else:

            percentage = 0

        remaining = max(
            target - current,
            0
        )

        result.append({

            "id":
                goal["id"],

            "name":
                goal["name"],

            "target":
                round(
                    target,
                    2
                ),

            "current":
                round(
                    current,
                    2
                ),

            "remaining":
                round(
                    remaining,
                    2
                ),

            "percentage":
                round(
                    percentage,
                    2
                ),

            "deadline":
                goal["deadline"]
        })

    return jsonify(result)


# =========================================================
# RECURRING EXPENSE DETECTION
# =========================================================

@app.route("/api/recurring")
def detect_recurring():

    connection = get_db_connection()

    transactions = connection.execute("""
        SELECT
            description,
            ROUND(amount, 2) AS amount,
            COUNT(*) AS occurrences

        FROM transactions

        WHERE type = 'expense'

        AND description IS NOT NULL

        AND TRIM(description) != ''

        GROUP BY
            LOWER(description),
            ROUND(amount, 2)

        HAVING COUNT(*) >= 3

        ORDER BY occurrences DESC
    """).fetchall()

    connection.close()

    return jsonify([

        {
            "description":
                row["description"],

            "amount":
                row["amount"],

            "occurrences":
                row["occurrences"]
        }

        for row in transactions
    ])


# =========================================================
# FINANCIAL HEALTH
# =========================================================

@app.route("/api/financial-health")
def financial_health():

    return jsonify(
        calculate_financial_health()
    )


# =========================================================
# CSV BANK STATEMENT UPLOAD
# =========================================================

@app.route(
    "/api/upload-statement",
    methods=["POST"]
)
def upload_statement():

    if "file" not in request.files:

        return jsonify({
            "success": False,
            "message":
                "No file uploaded"
        }), 400

    file = request.files["file"]

    if file.filename == "":

        return jsonify({
            "success": False,
            "message":
                "No file selected"
        }), 400

    if not file.filename.lower().endswith(".csv"):

        return jsonify({
            "success": False,
            "message":
                "Only CSV files are supported"
        }), 400

    safe_filename = os.path.basename(
        file.filename
    )

    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        safe_filename
    )

    file.save(filepath)

    try:

        dataframe = pd.read_csv(
            filepath
        )

    except Exception:

        return jsonify({
            "success": False,
            "message":
                "Could not read CSV file"
        }), 400

    required_columns = {
        "Date",
        "Description",
        "Amount",
        "Type"
    }

    if not required_columns.issubset(
        dataframe.columns
    ):

        return jsonify({

            "success": False,

            "message":
                "CSV must contain "
                "Date, Description, "
                "Amount and Type columns"
        }), 400

    connection = get_db_connection()

    imported = 0
    categorized = 0
    needs_review = 0
    skipped = 0

    for _, row in dataframe.iterrows():

        try:

            description = str(
                row["Description"]
            ).strip()

            transaction_type = (
                normalize_transaction_type(
                    row["Type"]
                )
            )

            if not transaction_type:

                skipped += 1
                continue

            amount = float(
                row["Amount"]
            )

            amount = abs(amount)

            transaction_date = normalize_date(
                row["Date"]
            )

            if amount <= 0:

                skipped += 1
                continue

            if not transaction_date:

                skipped += 1
                continue

            category = categorize_transaction(
                description
            )

            if category == "Other":

                needs_review += 1

            else:

                categorized += 1

            connection.execute("""
                INSERT INTO transactions
                (
                    type,
                    amount,
                    category,
                    description,
                    date
                )

                VALUES (?, ?, ?, ?, ?)
            """, (
                transaction_type,
                amount,
                category,
                description,
                transaction_date
            ))

            imported += 1

        except Exception:

            skipped += 1

    connection.commit()
    connection.close()

    return jsonify({

        "success": True,

        "message":
            f"{imported} transactions imported",

        "imported":
            imported,

        "categorized":
            categorized,

        "needs_review":
            needs_review,

        "skipped":
            skipped
    })


# =========================================================
# RESET DATABASE
# =========================================================

@app.route(
    "/api/reset-database",
    methods=["DELETE"]
)
def reset_database():

    connection = get_db_connection()

    connection.execute(
        "DELETE FROM transactions"
    )

    connection.execute(
        "DELETE FROM budgets"
    )

    connection.execute(
        "DELETE FROM goals"
    )

    connection.commit()
    connection.close()

    return jsonify({

        "success": True,

        "message":
            "Database reset"
    })


# =========================================================
# APPLICATION START
# =========================================================

if __name__ == "__main__":

    init_database()

    app.run(
        debug=True
    )