from flask import Flask, render_template, jsonify, request
import sqlite3
import pandas as pd
import os
import re
import json
import hashlib
from datetime import datetime, date
from collections import Counter
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# =========================================================
# FINFLOW — MONEY IN MOTION
# Backend
#
# Supports:
# - SQLite transactions, budgets and goals
# - CSV bank statements
# - PDF bank statements
# - Local transaction categorization
# - Optional AI parsing of statements
# - Optional AI Smart Coach
# - Recurring-expense detection
#
# AI is deliberately API-provider agnostic.
# Configure an OpenAI-compatible endpoint with:
#   AI_API_URL
#   AI_API_KEY
#   AI_MODEL
# =========================================================

app = Flask(__name__)

DATABASE = os.getenv("FINFLOW_DATABASE", "finance.db")
UPLOAD_FOLDER = os.getenv("FINFLOW_UPLOAD_FOLDER", "uploads")
MAX_UPLOAD_MB = int(os.getenv("FINFLOW_MAX_UPLOAD_MB", "10"))

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024


# =========================================================
# AI CONFIGURATION
# =========================================================

AI_API_URL = os.getenv("AI_API_URL", "").strip()
AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
AI_MODEL = os.getenv("AI_MODEL", "").strip()

# Only finance-related questions are allowed through the
# Smart Coach endpoint.
FINANCE_KEYWORDS = {
    "money", "finance", "financial", "income", "expense", "expenses",
    "spend", "spent", "spending", "saving", "savings", "save",
    "budget", "budgets", "goal", "goals", "transaction", "transactions",
    "salary", "balance", "cash", "cost", "costs", "bill", "bills",
    "subscription", "subscriptions", "recurring", "payment", "payments",
    "food", "transport", "shopping", "education", "entertainment",
    "health", "category", "categories", "afford", "affordability",
    "invest", "investment", "debt", "loan", "bank", "statement",
    "wealth", "emergency", "savings-rate", "net-worth"
}


# =========================================================
# CONSTANTS
# =========================================================

# Salary is an income category.
# The other eight categories are the expense categories used
# by the dashboard donut chart.
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

EXPENSE_CATEGORIES = [
    "Food",
    "Transport",
    "Shopping",
    "Education",
    "Bills",
    "Entertainment",
    "Health",
    "Other"
]

CATEGORY_KEYWORDS = {
    "Food": [
        "zomato", "swiggy", "restaurant", "food", "pizza", "cafe",
        "coffee", "bakery", "grocery", "groceries", "dining",
        "dominos", "kfc", "mcdonald", "burger", "canteen"
    ],
    "Transport": [
        "uber", "ola", "petrol", "fuel", "bus", "metro", "taxi",
        "rapido", "transport", "parking", "toll", "irctc", "railway",
        "flight", "airline", "diesel"
    ],
    "Shopping": [
        "amazon", "flipkart", "myntra", "shopping", "mall", "store",
        "retail", "meesho", "ajio", "clothing", "fashion"
    ],
    "Bills": [
        "jio", "airtel", "vi", "vodafone", "electricity", "recharge",
        "internet", "wifi", "bill", "utility", "water", "broadband",
        "mobile", "gas", "dth", "insurance"
    ],
    "Entertainment": [
        "netflix", "spotify", "movie", "cinema", "youtube", "prime",
        "entertainment", "game", "gaming", "hotstar", "disney",
        "bookmyshow"
    ],
    "Health": [
        "hospital", "pharmacy", "medical", "medicine", "doctor",
        "clinic", "health", "apollo", "diagnostic", "lab", "chemist"
    ],
    "Education": [
        "college", "course", "book", "education", "school", "university",
        "tuition", "exam", "udemy", "coursera", "fee", "fees"
    ],
    "Salary": [
        "salary", "payroll", "stipend", "wages", "income", "credited salary",
        "salary credit"
    ]
}

CATEGORY_ALIASES = {
    "food": "Food",
    "restaurant": "Food",
    "groceries": "Food",
    "grocery": "Food",
    "transport": "Transport",
    "travel": "Transport",
    "shopping": "Shopping",
    "education": "Education",
    "bill": "Bills",
    "bills": "Bills",
    "utilities": "Bills",
    "entertainment": "Entertainment",
    "health": "Health",
    "medical": "Health",
    "salary": "Salary",
    "income": "Salary",
    "other": "Other"
}


# =========================================================
# DATABASE
# =========================================================

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

    # Add import_hash to older databases without destroying
    # the user's existing transactions.
    columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(transactions)"
        ).fetchall()
    }

    if "import_hash" not in columns:
        connection.execute(
            "ALTER TABLE transactions ADD COLUMN import_hash TEXT"
        )

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_date
        ON transactions(date)
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_type
        ON transactions(type)
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_import_hash
        ON transactions(import_hash)
    """)

    connection.commit()
    connection.close()


# =========================================================
# GENERAL HELPERS
# =========================================================

def json_error(message, status=400, **extra):
    payload = {
        "success": False,
        "message": message
    }
    payload.update(extra)
    return jsonify(payload), status


def safe_float(value, default=None):
    if value is None:
        return default

    if isinstance(value, bool):
        return default

    try:
        if isinstance(value, str):
            cleaned = (
                value.replace(",", "")
                .replace("₹", "")
                .replace("$", "")
                .replace("€", "")
                .replace("£", "")
                .strip()
            )
            if not cleaned:
                return default
            return float(cleaned)
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_description(value):
    if value is None:
        return ""

    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_transaction_type(transaction_type):
    if transaction_type is None:
        return None

    value = str(transaction_type).strip().lower()

    if value in {
        "income", "credit", "credited", "deposit", "salary",
        "cr", "credit transaction"
    }:
        return "income"

    if value in {
        "expense", "debit", "debited", "withdrawal", "payment",
        "dr", "debit transaction"
    }:
        return "expense"

    return None


def normalize_date(value):
    if value is None or str(value).strip() == "":
        return None

    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")

    text = str(value).strip()

    # Remove common timestamp suffixes while keeping normal dates.
    text = re.sub(r"T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?$", "", text)

    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d.%m.%Y",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%Y/%m/%d",
        "%d-%b-%Y",
        "%d %b %Y",
        "%d-%B-%Y",
        "%d %B %Y"
    ]

    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass

    try:
        parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
        if pd.notna(parsed):
            return parsed.strftime("%Y-%m-%d")
    except Exception:
        pass

    return None


def month_name(month_number):
    names = [
        "January", "February", "March", "April",
        "May", "June", "July", "August",
        "September", "October", "November", "December"
    ]
    return names[month_number - 1]


def calculate_percentage_change(current, previous):
    current = float(current or 0)
    previous = float(previous or 0)

    if previous == 0:
        if current == 0:
            return 0
        return None

    return round(((current - previous) / abs(previous)) * 100, 2)


def get_requested_year():
    value = request.args.get("year")

    if value:
        try:
            return int(value)
        except (TypeError, ValueError):
            pass

    return datetime.now().year


def get_requested_month():
    value = request.args.get("month")

    if value and str(value).lower() != "all":
        try:
            month = int(value)
            if 1 <= month <= 12:
                return month
        except (TypeError, ValueError):
            pass

    return None


def month_range(year, month):
    start_date = f"{year}-{month:02d}-01"

    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    return start_date, end_date


def canonical_category(value):
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    if text in CATEGORIES:
        return text

    return CATEGORY_ALIASES.get(text.lower())


# =========================================================
# CATEGORIZATION
# =========================================================

def categorize_transaction(description, transaction_type=None):
    text = normalize_description(description).lower()

    if not text:
        return "Salary" if transaction_type == "income" else "Other"

    # Income should be checked first.
    if transaction_type == "income":
        for keyword in CATEGORY_KEYWORDS["Salary"]:
            if keyword in text:
                return "Salary"

    for category in EXPENSE_CATEGORIES:
        for keyword in CATEGORY_KEYWORDS.get(category, []):
            if keyword in text:
                return category

    # Some incoming payments may not explicitly say salary.
    if transaction_type == "income":
        for keyword in CATEGORY_KEYWORDS["Salary"]:
            if keyword in text:
                return "Salary"

    return "Other"


# =========================================================
# TRANSACTION DATABASE OPERATIONS
# =========================================================

def transaction_fingerprint(
    transaction_type,
    amount,
    category,
    description,
    transaction_date
):
    raw = "|".join([
        str(transaction_type or "").strip().lower(),
        f"{float(amount):.2f}",
        str(category or "").strip().lower(),
        normalize_description(description).lower(),
        str(transaction_date or "").strip()
    ])

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def insert_transaction(
    connection,
    transaction_type,
    amount,
    category,
    description,
    transaction_date,
    skip_duplicate=True
):
    fingerprint = transaction_fingerprint(
        transaction_type,
        amount,
        category,
        description,
        transaction_date
    )

    if skip_duplicate:
        existing = connection.execute(
            """
            SELECT id
            FROM transactions
            WHERE import_hash = ?
            LIMIT 1
            """,
            (fingerprint,)
        ).fetchone()

        if existing:
            return False, existing["id"]

    cursor = connection.execute(
        """
        INSERT INTO transactions
        (
            type,
            amount,
            category,
            description,
            date,
            import_hash
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            transaction_type,
            float(amount),
            category,
            normalize_description(description),
            transaction_date,
            fingerprint
        )
    )

    return True, cursor.lastrowid


# =========================================================
# FINANCIAL CALCULATIONS
# =========================================================

def get_month_summary(year, month):
    start_date, end_date = month_range(year, month)

    connection = get_db_connection()

    result = connection.execute(
        """
        SELECT
            COALESCE(
                SUM(
                    CASE
                        WHEN type = 'income' THEN amount
                        ELSE 0
                    END
                ),
                0
            ) AS income,
            COALESCE(
                SUM(
                    CASE
                        WHEN type = 'expense' THEN amount
                        ELSE 0
                    END
                ),
                0
            ) AS expenses
        FROM transactions
        WHERE date >= ?
          AND date < ?
        """,
        (start_date, end_date)
    ).fetchone()

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

    income_result = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM transactions
        WHERE type = 'income'
        """
    ).fetchone()

    expense_result = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM transactions
        WHERE type = 'expense'
        """
    ).fetchone()

    connection.close()

    total_income = float(income_result[0] or 0)
    total_expenses = float(expense_result[0] or 0)
    balance = total_income - total_expenses

    savings_rate = (
        (balance / total_income) * 100
        if total_income > 0
        else 0
    )

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

    return {
        "income": round(total_income, 2),
        "expenses": round(total_expenses, 2),
        "balance": round(balance, 2),
        "savings_rate": round(savings_rate, 2),
        "current_month": current_month,
        "current_year": current_year,
        "changes": {
            "balance": calculate_percentage_change(
                current["balance"],
                previous["balance"]
            ),
            "income": calculate_percentage_change(
                current["income"],
                previous["income"]
            ),
            "expenses": calculate_percentage_change(
                current["expenses"],
                previous["expenses"]
            ),
            "savings_rate": calculate_percentage_change(
                current["savings_rate"],
                previous["savings_rate"]
            )
        }
    }


# =========================================================
# SMART COACH — LOCAL INSIGHTS
# =========================================================

def generate_insights():
    insights = []

    connection = get_db_connection()

    budgets = connection.execute(
        """
        SELECT category, amount
        FROM budgets
        ORDER BY category
        """
    ).fetchall()

    now = datetime.now()
    year = now.year
    month = now.month
    start_date, next_date = month_range(year, month)

    for budget in budgets:
        spent = connection.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE type = 'expense'
              AND category = ?
              AND date >= ?
              AND date < ?
            """,
            (
                budget["category"],
                start_date,
                next_date
            )
        ).fetchone()[0]

        budget_amount = float(budget["amount"] or 0)
        spent = float(spent or 0)

        if budget_amount <= 0:
            continue

        percentage = (spent / budget_amount) * 100

        if percentage > 100:
            insights.append({
                "type": "danger",
                "title": "Budget Exceeded",
                "message": (
                    f"You exceeded your {budget['category']} "
                    f"budget by ₹{spent - budget_amount:.2f}."
                )
            })
        elif percentage >= 80:
            insights.append({
                "type": "warning",
                "title": "Budget Alert",
                "message": (
                    f"You have used {percentage:.0f}% of your "
                    f"{budget['category']} budget."
                )
            })

    connection.close()

    summary = calculate_financial_summary()

    if summary["income"] > 0:
        if summary["savings_rate"] < 20:
            insights.append({
                "type": "warning",
                "title": "Savings Opportunity",
                "message": (
                    "Your current savings rate is below 20%. "
                    "Review your largest discretionary categories."
                )
            })
        elif summary["savings_rate"] >= 30:
            insights.append({
                "type": "positive",
                "title": "Strong Savings",
                "message": (
                    f"You're currently saving "
                    f"{summary['savings_rate']:.1f}% of your income."
                )
            })

    connection = get_db_connection()

    largest_category = connection.execute(
        """
        SELECT category, SUM(amount) AS total
        FROM transactions
        WHERE type = 'expense'
        GROUP BY category
        ORDER BY total DESC
        LIMIT 1
        """
    ).fetchone()

    connection.close()

    if largest_category:
        insights.append({
            "type": "info",
            "title": "Spending Insight",
            "message": (
                f"Your highest spending category is "
                f"{largest_category['category']} at "
                f"₹{float(largest_category['total'] or 0):.2f}."
            )
        })

    if not insights:
        insights.append({
            "type": "info",
            "title": "Getting Started",
            "message": (
                "Add transactions, budgets or a bank statement "
                "to receive personalized financial insights."
            )
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


# =========================================================
# RECURRING EXPENSE DETECTION
# =========================================================

def normalize_recurring_key(description):
    text = normalize_description(description).lower()

    # Remove transaction IDs/reference numbers and excess digits.
    text = re.sub(r"\b(?:txn|transaction|ref|utr|rrn|id)\s*[:#-]?\s*\w+\b", "", text)
    text = re.sub(r"\b\d{4,}\b", "", text)
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def get_recurring_expenses():
    connection = get_db_connection()

    rows = connection.execute(
        """
        SELECT id, amount, description, date, category
        FROM transactions
        WHERE type = 'expense'
          AND description IS NOT NULL
          AND TRIM(description) != ''
        ORDER BY date ASC, id ASC
        """
    ).fetchall()

    connection.close()

    groups = {}

    for row in rows:
        key = normalize_recurring_key(row["description"])

        if not key:
            continue

        groups.setdefault(key, []).append(dict(row))

    recurring = []

    for key, items in groups.items():
        if len(items) < 2:
            continue

        amounts = [float(item["amount"]) for item in items]
        median_amount = float(pd.Series(amounts).median())

        # Recurring payments normally have similar amounts.
        tolerance = max(5.0, median_amount * 0.10)
        similar_items = [
            item
            for item in items
            if abs(float(item["amount"]) - median_amount) <= tolerance
        ]

        if len(similar_items) < 2:
            continue

        dates = []
        for item in similar_items:
            parsed = pd.to_datetime(
                item["date"],
                errors="coerce"
            )
            if pd.notna(parsed):
                dates.append(parsed)

        if len(dates) >= 2:
            dates = sorted(dates)
            gaps = [
                (dates[i] - dates[i - 1]).days
                for i in range(1, len(dates))
            ]

            avg_gap = sum(gaps) / len(gaps)
            is_periodic = (
                20 <= avg_gap <= 45
                or 6 <= avg_gap <= 10
                or 85 <= avg_gap <= 100
            )
        else:
            avg_gap = None
            is_periodic = False

        # Two or more similar payments are enough for a useful
        # "possible recurring" signal. Three or more periodic
        # payments are marked as higher confidence.
        if len(similar_items) >= 3:
            confidence = "high" if is_periodic else "medium"
        else:
            confidence = "possible" if is_periodic else "possible"

        latest = similar_items[-1]

        if avg_gap and 20 <= avg_gap <= 45:
            frequency = "monthly"
            estimated_monthly = median_amount
        elif avg_gap and 6 <= avg_gap <= 10:
            frequency = "weekly"
            estimated_monthly = median_amount * 4.33
        elif avg_gap and 85 <= avg_gap <= 100:
            frequency = "quarterly"
            estimated_monthly = median_amount / 3
        else:
            frequency = "repeated"
            estimated_monthly = median_amount

        recurring.append({
            "description": latest["description"],
            "normalized_description": key,
            "category": latest["category"],
            "amount": round(median_amount, 2),
            "occurrences": len(similar_items),
            "frequency": frequency,
            "estimated_monthly": round(estimated_monthly, 2),
            "confidence": confidence,
            "last_date": latest["date"]
        })

    recurring.sort(
        key=lambda item: item["estimated_monthly"],
        reverse=True
    )

    return recurring


# =========================================================
# BANK STATEMENT — COLUMN DETECTION
# =========================================================

def normalize_column_name(value):
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def find_column(columns, candidates):
    normalized = {
        normalize_column_name(column): column
        for column in columns
    }

    # Exact normalized matches first.
    for candidate in candidates:
        candidate_normalized = normalize_column_name(candidate)
        if candidate_normalized in normalized:
            return normalized[candidate_normalized]

    # Partial matches.
    for normalized_name, original_name in normalized.items():
        for candidate in candidates:
            candidate_normalized = normalize_column_name(candidate)
            if candidate_normalized in normalized_name:
                return original_name

    return None


def parse_amount(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return abs(float(value))

    text = str(value).strip()

    if not text:
        return None

    negative = (
        text.startswith("-")
        or text.startswith("(")
        or text.lower().endswith("dr")
    )

    cleaned = (
        text.replace(",", "")
        .replace("₹", "")
        .replace("$", "")
        .replace("€", "")
        .replace("£", "")
        .replace("INR", "")
        .replace("Rs.", "")
        .replace("Rs", "")
        .replace("CR", "")
        .replace("DR", "")
        .replace("cr", "")
        .replace("dr", "")
        .replace("(", "")
        .replace(")", "")
        .strip()
    )

    try:
        amount = abs(float(cleaned))
        return -amount if negative else amount
    except ValueError:
        return None


def infer_type_from_row(row, amount_value=None):
    type_column = find_column(
        row.index,
        [
            "Type", "Transaction Type", "Txn Type",
            "Credit Debit", "Dr Cr", "Direction"
        ]
    )

    if type_column:
        explicit = normalize_transaction_type(row[type_column])
        if explicit:
            return explicit

        text = str(row[type_column]).lower()
        if "credit" in text or text.strip() == "cr":
            return "income"
        if "debit" in text or text.strip() == "dr":
            return "expense"

    credit_column = find_column(
        row.index,
        ["Credit", "Credits", "Credit Amount"]
    )
    debit_column = find_column(
        row.index,
        ["Debit", "Debits", "Debit Amount"]
    )

    credit_value = parse_amount(row[credit_column]) if credit_column else None
    debit_value = parse_amount(row[debit_column]) if debit_column else None

    if credit_value and credit_value > 0:
        return "income"

    if debit_value and debit_value > 0:
        return "expense"

    if amount_value is not None:
        return "income" if amount_value > 0 else "expense"

    return None


def dataframe_to_transactions(dataframe):
    dataframe = dataframe.copy()
    dataframe.columns = [
        str(column).strip()
        for column in dataframe.columns
    ]

    date_column = find_column(
        dataframe.columns,
        [
            "Date", "Transaction Date", "Txn Date",
            "Value Date", "Posting Date", "Posted Date"
        ]
    )

    description_column = find_column(
        dataframe.columns,
        [
            "Description", "Narration", "Details", "Particulars",
            "Transaction Description", "Remarks", "Merchant",
            "Reference", "Memo"
        ]
    )

    amount_column = find_column(
        dataframe.columns,
        [
            "Amount", "Transaction Amount", "Txn Amount",
            "Value", "Amount INR"
        ]
    )

    if not date_column:
        raise ValueError(
            "Could not find a date column in the statement."
        )

    if not description_column:
        raise ValueError(
            "Could not find a description/narration column in the statement."
        )

    credit_column = find_column(
        dataframe.columns,
        ["Credit", "Credits", "Credit Amount"]
    )

    debit_column = find_column(
        dataframe.columns,
        ["Debit", "Debits", "Debit Amount"]
    )

    if not amount_column and not credit_column and not debit_column:
        raise ValueError(
            "Could not find an amount, credit or debit column."
        )

    parsed_transactions = []

    for _, row in dataframe.iterrows():
        transaction_date = normalize_date(row.get(date_column))

        if not transaction_date:
            continue

        description = normalize_description(
            row.get(description_column, "")
        )

        amount = None

        if amount_column:
            amount = parse_amount(row.get(amount_column))

        credit_value = (
            parse_amount(row.get(credit_column))
            if credit_column
            else None
        )

        debit_value = (
            parse_amount(row.get(debit_column))
            if debit_column
            else None
        )

        transaction_type = infer_type_from_row(
            row,
            amount
        )

        if credit_value and credit_value > 0:
            transaction_type = "income"
            amount = abs(credit_value)

        elif debit_value and debit_value > 0:
            transaction_type = "expense"
            amount = abs(debit_value)

        elif amount is not None:
            # If the source provides a signed amount, preserve its
            # direction. For unsigned amounts, use the Type column.
            type_column = find_column(
                row.index,
                [
                    "Type", "Transaction Type", "Txn Type",
                    "Credit Debit", "Dr Cr", "Direction"
                ]
            )

            if type_column:
                explicit = normalize_transaction_type(
                    row.get(type_column)
                )
                if explicit:
                    transaction_type = explicit

            if transaction_type is None:
                transaction_type = (
                    "income" if float(amount) > 0 else "expense"
                )

            amount = abs(float(amount))

        if not transaction_type or amount is None or amount <= 0:
            continue

        category_column = find_column(
            row.index,
            ["Category", "Transaction Category", "Expense Category"]
        )

        category = (
            canonical_category(row.get(category_column))
            if category_column
            else None
        )

        if category is None:
            category = categorize_transaction(
                description,
                transaction_type
            )

        if transaction_type == "income":
            category = "Salary" if category == "Other" else category
        elif category == "Salary":
            category = "Other"

        parsed_transactions.append({
            "type": transaction_type,
            "amount": round(float(amount), 2),
            "category": category,
            "description": description,
            "date": transaction_date
        })

    return parsed_transactions


# =========================================================
# CSV PARSER
# =========================================================

def parse_csv_statement(filepath):
    last_error = None

    # Try normal CSV parsing first, then common encodings.
    for encoding in ["utf-8-sig", "utf-8", "cp1252", "latin1"]:
        try:
            dataframe = pd.read_csv(
                filepath,
                encoding=encoding,
                sep=None,
                engine="python"
            )

            if dataframe.shape[1] >= 2:
                return dataframe_to_transactions(dataframe)

        except Exception as exc:
            last_error = exc

    raise ValueError(
        f"Could not parse CSV statement: {last_error}"
    )


# =========================================================
# PDF PARSER
# =========================================================

def extract_pdf_text(filepath):
    if PdfReader is None:
        raise RuntimeError(
            "PyPDF2 is not installed. Run: pip install -r requirements.txt"
        )

    reader = PdfReader(filepath)

    pages = []

    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""

        if text.strip():
            pages.append(text)

    return "\n".join(pages).strip()


def parse_money_from_text(value):
    if value is None:
        return None

    cleaned = str(value)
    cleaned = (
        cleaned.replace(",", "")
        .replace("₹", "")
        .replace("INR", "")
        .replace("Rs.", "")
        .replace("Rs", "")
        .strip()
    )

    match = re.search(
        r"-?\d+(?:\.\d{1,2})?",
        cleaned
    )

    if not match:
        return None

    try:
        return float(match.group())
    except ValueError:
        return None


def parse_pdf_lines_heuristically(text):
    """
    Fallback parser for text-based PDFs.

    It looks for:
      date + description + amount
    or:
      date + description + debit + credit

    Bank PDFs differ substantially, so this is intentionally
    conservative. If an AI API is configured, AI parsing is
    attempted before this fallback.
    """
    transactions = []

    date_pattern = re.compile(
        r"(?P<date>"
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"
        r"|"
        r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b"
        r"|"
        r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b"
        r")"
    )

    amount_pattern = re.compile(
        r"(?:₹|INR|Rs\.?|)\s*"
        r"-?\d[\d,]*(?:\.\d{1,2})?"
        r"(?:\s*(?:CR|DR))?",
        re.IGNORECASE
    )

    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in text.splitlines()
        if line.strip()
    ]

    for line in lines:
        date_match = date_pattern.search(line)

        if not date_match:
            continue

        parsed_date = normalize_date(
            date_match.group("date")
        )

        if not parsed_date:
            continue

        remainder = (
            line[:date_match.start()]
            + " "
            + line[date_match.end():]
        ).strip()

        amount_matches = list(
            amount_pattern.finditer(remainder)
        )

        if not amount_matches:
            continue

        # Take the final numeric value as the most likely amount.
        # This avoids treating dates/reference numbers as amounts.
        selected = amount_matches[-1]
        amount = parse_money_from_text(
            selected.group()
        )

        if amount is None or amount <= 0:
            continue

        description = (
            remainder[:selected.start()]
            + " "
            + remainder[selected.end():]
        ).strip()

        description = re.sub(
            r"\b(?:CR|DR)\b",
            "",
            description,
            flags=re.IGNORECASE
        ).strip()

        if len(description) < 2:
            description = "Bank transaction"

        # Direction hints.
        lowered = line.lower()

        if (
            "credit" in lowered
            or "credited" in lowered
            or re.search(r"\bcr\b", lowered)
            or "deposit" in lowered
            or "salary" in lowered
        ):
            transaction_type = "income"
        elif (
            "debit" in lowered
            or "debited" in lowered
            or re.search(r"\bdr\b", lowered)
            or "withdraw" in lowered
            or "payment" in lowered
        ):
            transaction_type = "expense"
        else:
            # Conservative fallback: most bank statement rows are
            # expenses when no direction is available.
            transaction_type = "expense"

        category = categorize_transaction(
            description,
            transaction_type
        )

        transactions.append({
            "type": transaction_type,
            "amount": round(amount, 2),
            "category": category,
            "description": description,
            "date": parsed_date
        })

    return transactions


# =========================================================
# AI CLIENT
# =========================================================

def ai_is_configured():
    return bool(
        AI_API_URL
        and AI_API_KEY
        and AI_MODEL
    )


def call_ai(messages, temperature=0.2, max_tokens=1500):
    """
    Calls an OpenAI-compatible /v1/chat/completions-style endpoint.

    The endpoint, key and model are configured through environment
    variables so FinFlow is not tied to one provider.
    """
    if not ai_is_configured():
        return None, "AI is not configured."

    payload = {
        "model": AI_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    body = json.dumps(payload).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AI_API_KEY}"
    }

    req = urlrequest.Request(
        AI_API_URL,
        data=body,
        headers=headers,
        method="POST"
    )

    try:
        with urlrequest.urlopen(req, timeout=45) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw)

        choices = data.get("choices") or []

        if not choices:
            return None, "AI provider returned no choices."

        message = choices[0].get("message") or {}
        content = message.get("content")

        if isinstance(content, list):
            content = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict)
            )

        if not content:
            return None, "AI provider returned an empty response."

        return str(content).strip(), None

    except HTTPError as exc:
        try:
            details = exc.read().decode("utf-8")
        except Exception:
            details = str(exc)

        return None, f"AI provider error: {details[:500]}"

    except URLError as exc:
        return None, f"AI connection error: {exc}"

    except Exception as exc:
        return None, f"AI request failed: {exc}"


def extract_json_from_ai(text):
    if not text:
        return None

    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(
            r"^```(?:json)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE
        )
        cleaned = re.sub(
            r"\s*```$",
            "",
            cleaned
        ).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try extracting the first JSON object/array.
    object_match = re.search(
        r"(\{.*\}|\[.*\])",
        cleaned,
        flags=re.DOTALL
    )

    if object_match:
        try:
            return json.loads(
                object_match.group(1)
            )
        except json.JSONDecodeError:
            return None

    return None


def ai_parse_statement_text(text):
    if not ai_is_configured():
        return None, "AI is not configured."

    # Avoid sending an unnecessarily enormous statement to an API.
    # Keep the beginning and end because some statements put
    # headers at the beginning and summaries at the end.
    max_chars = 60000

    if len(text) > max_chars:
        text_for_ai = (
            text[:45000]
            + "\n\n[...middle of document omitted...]\n\n"
            + text[-15000:]
        )
    else:
        text_for_ai = text

    system_prompt = """
You are FinFlow's bank-statement extraction engine.

Your ONLY job is to convert bank-statement text into transaction
records.

Return ONLY valid JSON. No markdown.

Return this exact structure:
{
  "transactions": [
    {
      "date": "YYYY-MM-DD",
      "description": "merchant or narration",
      "amount": 123.45,
      "type": "income",
      "category": "Salary"
    }
  ]
}

Allowed type values:
- income
- expense

Allowed categories:
- Food
- Transport
- Shopping
- Education
- Bills
- Entertainment
- Health
- Salary
- Other

Rules:
1. Never invent a transaction.
2. Ignore opening balance, closing balance, running balance,
   page numbers, account numbers and summaries unless they are
   clearly actual transactions.
3. Use the transaction date, not the statement generation date.
4. Amount must be positive.
5. Infer income/expense only when the statement provides enough
   evidence.
6. If a category is uncertain, use Other.
7. Keep the merchant/narration concise.
8. Return an empty transactions array if no reliable transactions
   can be extracted.
"""

    user_prompt = (
        "Extract the bank transactions from this statement text.\n\n"
        + text_for_ai
    )

    response, error = call_ai(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0,
        max_tokens=8000
    )

    if error:
        return None, error

    parsed = extract_json_from_ai(response)

    if not isinstance(parsed, dict):
        return None, "AI returned invalid transaction JSON."

    raw_transactions = parsed.get("transactions")

    if not isinstance(raw_transactions, list):
        return None, "AI response did not contain transactions."

    cleaned = []

    for item in raw_transactions:
        if not isinstance(item, dict):
            continue

        transaction_date = normalize_date(
            item.get("date")
        )

        amount = safe_float(
            item.get("amount")
        )

        transaction_type = normalize_transaction_type(
            item.get("type")
        )

        description = normalize_description(
            item.get("description")
        )

        category = canonical_category(
            item.get("category")
        )

        if not transaction_date:
            continue

        if amount is None or amount <= 0:
            continue

        if not transaction_type:
            continue

        if not description:
            description = "Bank transaction"

        if transaction_type == "income":
            category = category or "Salary"
        else:
            category = category or categorize_transaction(
                description,
                transaction_type
            )

            if category == "Salary":
                category = "Other"

        cleaned.append({
            "type": transaction_type,
            "amount": round(abs(amount), 2),
            "category": category,
            "description": description,
            "date": transaction_date
        })

    return cleaned, None


# =========================================================
# AI SMART COACH CONTEXT
# =========================================================

def get_financial_context():
    summary = calculate_financial_summary()
    recurring = get_recurring_expenses()

    connection = get_db_connection()

    category_rows = connection.execute(
        """
        SELECT category, SUM(amount) AS total
        FROM transactions
        WHERE type = 'expense'
        GROUP BY category
        ORDER BY total DESC
        """
    ).fetchall()

    recent_rows = connection.execute(
        """
        SELECT type, amount, category, description, date
        FROM transactions
        ORDER BY date DESC, id DESC
        LIMIT 20
        """
    ).fetchall()

    budgets = connection.execute(
        """
        SELECT category, amount
        FROM budgets
        ORDER BY category
        """
    ).fetchall()

    goals = connection.execute(
        """
        SELECT name, target, current, deadline
        FROM goals
        ORDER BY id DESC
        """
    ).fetchall()

    connection.close()

    category_spending = {
        row["category"]: round(
            float(row["total"] or 0),
            2
        )
        for row in category_rows
    }

    return {
        "summary": summary,
        "category_spending": category_spending,
        "budgets": [
            {
                "category": row["category"],
                "amount": float(row["amount"])
            }
            for row in budgets
        ],
        "goals": [
            {
                "name": row["name"],
                "target": float(row["target"]),
                "current": float(row["current"]),
                "deadline": row["deadline"]
            }
            for row in goals
        ],
        "recurring_expenses": recurring[:20],
        "recent_transactions": [
            {
                "type": row["type"],
                "amount": float(row["amount"]),
                "category": row["category"],
                "description": row["description"],
                "date": row["date"]
            }
            for row in recent_rows
        ]
    }


def is_finance_question(message):
    text = str(message or "").lower()

    if not text.strip():
        return False

    tokens = set(
        re.findall(r"[a-zA-Z][a-zA-Z-]+", text)
    )

    return bool(tokens.intersection(FINANCE_KEYWORDS))


def local_financial_answer(message):
    """
    Useful fallback when no AI API is configured.
    This keeps Smart Coach functional even before the API key
    is added.
    """
    text = str(message or "").lower()
    context = get_financial_context()
    summary = context["summary"]

    if "balance" in text:
        return (
            f"Your current overall balance is "
            f"₹{summary['balance']:,.2f}."
        )

    if "income" in text or "salary" in text:
        return (
            f"Your total recorded income is "
            f"₹{summary['income']:,.2f}."
        )

    if "expense" in text or "spent" in text or "spending" in text:
        return (
            f"Your total recorded expenses are "
            f"₹{summary['expenses']:,.2f}. "
            f"Your savings rate is "
            f"{summary['savings_rate']:.1f}%."
        )

    if "saving" in text:
        return (
            f"Your current savings rate is "
            f"{summary['savings_rate']:.1f}%, with "
            f"₹{summary['balance']:,.2f} remaining after "
            f"recorded expenses."
        )

    if "recurring" in text or "subscription" in text:
        recurring = context["recurring_expenses"]

        if not recurring:
            return "I couldn't identify any recurring expenses yet."

        top = recurring[:5]
        lines = [
            f"{item['description']}: "
            f"₹{item['estimated_monthly']:,.2f}/month"
            for item in top
        ]

        return "Possible recurring expenses:\n" + "\n".join(lines)

    if "food" in text:
        value = context["category_spending"].get("Food", 0)
        return f"Recorded Food spending is ₹{value:,.2f}."

    if "transport" in text:
        value = context["category_spending"].get("Transport", 0)
        return f"Recorded Transport spending is ₹{value:,.2f}."

    if "shopping" in text:
        value = context["category_spending"].get("Shopping", 0)
        return f"Recorded Shopping spending is ₹{value:,.2f}."

    if "budget" in text:
        budgets = context["budgets"]

        if not budgets:
            return "You have not created any budgets yet."

        parts = []
        for budget in budgets:
            parts.append(
                f"{budget['category']}: "
                f"₹{budget['amount']:,.2f}"
            )

        return "Your current budgets are:\n" + "\n".join(parts)

    return (
        "I can help with your FinFlow finances. Try asking "
        "about spending, income, balance, budgets, savings, "
        "recurring expenses or a category such as Food."
    )


def ai_financial_answer(message):
    if not is_finance_question(message):
        return {
            "success": False,
            "message": (
                "FinFlow AI is limited to finance-related "
                "questions."
            ),
            "answer": (
                "I can help only with your FinFlow financial "
                "data, such as spending, income, budgets, "
                "savings and recurring expenses."
            ),
            "ai_used": False
        }

    context = get_financial_context()

    if not ai_is_configured():
        return {
            "success": True,
            "message": "Local financial assistant used.",
            "answer": local_financial_answer(message),
            "ai_used": False
        }

    system_prompt = """
You are FinFlow Smart Coach, a personal-finance analysis assistant.

Answer ONLY finance-related questions.

Use the supplied FinFlow data as the source of truth for
personalized numbers. Do not invent transactions, balances,
budgets or goals.

You may:
- explain spending
- compare categories
- identify patterns
- discuss budgets
- discuss savings
- discuss recurring expenses
- answer questions about the user's recorded transactions
- provide general educational financial guidance

You must NOT:
- claim to have access to bank accounts
- invent missing financial data
- execute financial transactions
- give instructions to evade laws or financial controls
- present uncertain calculations as certain

Keep answers concise, practical and understandable.
If a number is not present in the data, say that it is not
available rather than guessing.

This is an analysis assistant, not a licensed financial adviser.
"""

    user_prompt = (
        "FinFlow financial context:\n"
        + json.dumps(context, ensure_ascii=False, indent=2)
        + "\n\nUser question:\n"
        + str(message).strip()
    )

    answer, error = call_ai(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.2,
        max_tokens=1200
    )

    if error:
        # Graceful fallback keeps the app usable if the external
        # AI service is unavailable.
        return {
            "success": True,
            "message": "AI service unavailable; local analysis used.",
            "answer": local_financial_answer(message),
            "ai_used": False,
            "ai_error": error
        }

    return {
        "success": True,
        "message": "FinFlow AI response generated.",
        "answer": answer,
        "ai_used": True
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
        "status": "success",
        "ai_configured": ai_is_configured()
    })


# =========================================================
# TRANSACTIONS
# =========================================================

@app.route("/api/transactions", methods=["POST"])
def add_transaction():
    data = request.get_json(silent=True) or {}

    transaction_type = normalize_transaction_type(
        data.get("type")
    )

    amount = safe_float(data.get("amount"))
    category = canonical_category(data.get("category"))
    description = normalize_description(
        data.get("description", "")
    )
    transaction_date = normalize_date(
        data.get("date")
    )

    if not transaction_type:
        return json_error(
            "Type must be income or expense."
        )

    if amount is None or amount <= 0:
        return json_error(
            "Amount must be greater than zero."
        )

    if not transaction_date:
        return json_error(
            "A valid date is required."
        )

    if not category:
        category = categorize_transaction(
            description,
            transaction_type
        )

    if transaction_type == "income":
        category = "Salary" if category == "Other" else category
    elif category == "Salary":
        category = "Other"

    connection = get_db_connection()

    inserted, transaction_id = insert_transaction(
        connection,
        transaction_type,
        amount,
        category,
        description,
        transaction_date,
        skip_duplicate=False
    )

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "message": "Transaction added successfully.",
        "id": transaction_id
    })


@app.route("/api/transactions", methods=["GET"])
def get_transactions():
    connection = get_db_connection()

    rows = connection.execute(
        """
        SELECT id, type, amount, category, description, date
        FROM transactions
        ORDER BY date DESC, id DESC
        """
    ).fetchall()

    connection.close()

    return jsonify([
        dict(row)
        for row in rows
    ])


@app.route(
    "/api/transactions/<int:transaction_id>",
    methods=["PUT"]
)
def update_transaction(transaction_id):
    data = request.get_json(silent=True) or {}

    transaction_type = normalize_transaction_type(
        data.get("type")
    )
    amount = safe_float(data.get("amount"))
    category = canonical_category(
        data.get("category")
    )
    description = normalize_description(
        data.get("description", "")
    )
    transaction_date = normalize_date(
        data.get("date")
    )

    if not transaction_type:
        return json_error(
            "Invalid transaction type."
        )

    if amount is None or amount <= 0:
        return json_error(
            "Amount must be greater than zero."
        )

    if not transaction_date:
        return json_error(
            "Invalid date."
        )

    if not category:
        category = categorize_transaction(
            description,
            transaction_type
        )

    if transaction_type == "income":
        category = "Salary" if category == "Other" else category
    elif category == "Salary":
        category = "Other"

    connection = get_db_connection()

    cursor = connection.execute(
        """
        UPDATE transactions
        SET
            type = ?,
            amount = ?,
            category = ?,
            description = ?,
            date = ?,
            import_hash = NULL
        WHERE id = ?
        """,
        (
            transaction_type,
            amount,
            category,
            description,
            transaction_date,
            transaction_id
        )
    )

    connection.commit()
    connection.close()

    if cursor.rowcount == 0:
        return json_error(
            "Transaction not found.",
            404
        )

    return jsonify({
        "success": True,
        "message": "Transaction updated."
    })


@app.route(
    "/api/transactions/<int:transaction_id>",
    methods=["DELETE"]
)
def delete_transaction(transaction_id):
    connection = get_db_connection()

    cursor = connection.execute(
        """
        DELETE FROM transactions
        WHERE id = ?
        """,
        (transaction_id,)
    )

    connection.commit()
    connection.close()

    if cursor.rowcount == 0:
        return json_error(
            "Transaction not found.",
            404
        )

    return jsonify({
        "success": True,
        "message": "Transaction deleted."
    })


# =========================================================
# CATEGORIZATION
# =========================================================

@app.route("/api/categorize", methods=["POST"])
def categorize():
    data = request.get_json(silent=True) or {}

    description = normalize_description(
        data.get("description", "")
    )

    transaction_type = normalize_transaction_type(
        data.get("type")
    )

    category = categorize_transaction(
        description,
        transaction_type
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

    recent_transactions = connection.execute(
        """
        SELECT id, type, amount, category, description, date
        FROM transactions
        ORDER BY date DESC, id DESC
        LIMIT 5
        """
    ).fetchall()

    connection.close()

    return jsonify({
        "summary": summary,
        "recent_transactions": [
            dict(transaction)
            for transaction in recent_transactions
        ],
        "insights": generate_insights(),
        "health": calculate_financial_health(),
        "recurring_expenses": get_recurring_expenses()[:5]
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
        start_date, end_date = month_range(
            year,
            month
        )

        rows = connection.execute(
            """
            SELECT
                category,
                COALESCE(SUM(amount), 0) AS total
            FROM transactions
            WHERE type = 'expense'
              AND date >= ?
              AND date < ?
            GROUP BY category
            ORDER BY total DESC
            """,
            (
                start_date,
                end_date
            )
        ).fetchall()

    else:
        rows = connection.execute(
            """
            SELECT
                category,
                COALESCE(SUM(amount), 0) AS total
            FROM transactions
            WHERE type = 'expense'
              AND strftime('%Y', date) = ?
            GROUP BY category
            ORDER BY total DESC
            """,
            (str(year),)
        ).fetchall()

    connection.close()

    data = {
        category: 0
        for category in EXPENSE_CATEGORIES
    }

    for row in rows:
        category = row["category"]

        if category in data:
            data[category] = round(
                float(row["total"] or 0),
                2
            )

    return jsonify([
        {
            "category": category,
            "total": total
        }
        for category, total in data.items()
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

    rows = connection.execute(
        """
        SELECT
            CAST(strftime('%m', date) AS INTEGER) AS month,
            COALESCE(
                SUM(
                    CASE
                        WHEN type = 'income' THEN amount
                        ELSE 0
                    END
                ),
                0
            ) AS income,
            COALESCE(
                SUM(
                    CASE
                        WHEN type = 'expense' THEN amount
                        ELSE 0
                    END
                ),
                0
            ) AS expenses
        FROM transactions
        WHERE strftime('%Y', date) = ?
        GROUP BY strftime('%m', date)
        ORDER BY month
        """,
        (str(year),)
    ).fetchall()

    connection.close()

    monthly_data = {}

    for row in rows:
        month_number = int(row["month"])

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
            "month_name": month_name(month_number),
            "year": year,
            "income": values["income"],
            "expenses": values["expenses"]
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
            "income": calculate_percentage_change(
                current["income"],
                previous["income"]
            ),
            "expenses": calculate_percentage_change(
                current["expenses"],
                previous["expenses"]
            ),
            "balance": calculate_percentage_change(
                current["balance"],
                previous["balance"]
            ),
            "savings_rate": calculate_percentage_change(
                current["savings_rate"],
                previous["savings_rate"]
            )
        }
    })


# =========================================================
# BUDGETS
# =========================================================

@app.route("/api/budgets", methods=["POST"])
def add_budget():
    data = request.get_json(silent=True) or {}

    category = canonical_category(
        data.get("category")
    )
    amount = safe_float(
        data.get("amount")
    )

    if not category:
        return json_error(
            "Category is required."
        )

    if category == "Salary":
        return json_error(
            "Salary cannot be used as an expense budget."
        )

    if amount is None or amount <= 0:
        return json_error(
            "Budget amount must be greater than zero."
        )

    connection = get_db_connection()

    connection.execute(
        """
        INSERT INTO budgets(category, amount)
        VALUES (?, ?)
        ON CONFLICT(category)
        DO UPDATE SET amount = excluded.amount
        """,
        (
            category,
            amount
        )
    )

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "message": "Budget saved."
    })


@app.route("/api/budgets", methods=["GET"])
def get_budgets():
    connection = get_db_connection()

    budgets = connection.execute(
        """
        SELECT *
        FROM budgets
        ORDER BY category
        """
    ).fetchall()

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

    cursor = connection.execute(
        """
        DELETE FROM budgets
        WHERE category = ?
        """,
        (category,)
    )

    connection.commit()
    connection.close()

    if cursor.rowcount == 0:
        return json_error(
            "Budget not found.",
            404
        )

    return jsonify({
        "success": True,
        "message": "Budget deleted."
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

    start_date, end_date = month_range(
        year,
        month
    )

    connection = get_db_connection()

    budgets = connection.execute(
        """
        SELECT category, amount
        FROM budgets
        ORDER BY category
        """
    ).fetchall()

    result = []

    for budget in budgets:
        spending = connection.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE type = 'expense'
              AND category = ?
              AND date >= ?
              AND date < ?
            """,
            (
                budget["category"],
                start_date,
                end_date
            )
        ).fetchone()[0]

        budget_amount = float(
            budget["amount"] or 0
        )
        spending = float(
            spending or 0
        )

        percentage = (
            (spending / budget_amount) * 100
            if budget_amount > 0
            else 0
        )

        result.append({
            "category": budget["category"],
            "budget": round(
                budget_amount,
                2
            ),
            "spent": round(
                spending,
                2
            ),
            "percentage": round(
                percentage,
                2
            ),
            "remaining": round(
                budget_amount - spending,
                2
            )
        })

    connection.close()

    return jsonify(result)


# =========================================================
# GOALS
# =========================================================

@app.route("/api/goals", methods=["POST"])
def add_goal():
    data = request.get_json(silent=True) or {}

    name = normalize_description(
        data.get("name")
    )
    target = safe_float(
        data.get("target")
    )
    current = safe_float(
        data.get("current"),
        0
    )
    deadline = data.get("deadline")

    if not name:
        return json_error(
            "Goal name is required."
        )

    if target is None or target <= 0:
        return json_error(
            "Target must be greater than zero."
        )

    current = max(
        0,
        min(
            current,
            target
        )
    )

    if deadline:
        deadline = normalize_date(
            deadline
        )

    connection = get_db_connection()

    cursor = connection.execute(
        """
        INSERT INTO goals
        (
            name,
            target,
            current,
            deadline
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            name,
            target,
            current,
            deadline
        )
    )

    connection.commit()

    goal_id = cursor.lastrowid

    connection.close()

    return jsonify({
        "success": True,
        "message": "Goal created.",
        "id": goal_id
    })


@app.route("/api/goals", methods=["GET"])
def get_goals():
    connection = get_db_connection()

    goals = connection.execute(
        """
        SELECT *
        FROM goals
        ORDER BY id DESC
        """
    ).fetchall()

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
    data = request.get_json(silent=True) or {}

    connection = get_db_connection()

    existing = connection.execute(
        """
        SELECT *
        FROM goals
        WHERE id = ?
        """,
        (goal_id,)
    ).fetchone()

    if not existing:
        connection.close()
        return json_error(
            "Goal not found.",
            404
        )

    name = normalize_description(
        data.get(
            "name",
            existing["name"]
        )
    )

    target = safe_float(
        data.get(
            "target",
            existing["target"]
        )
    )

    current = safe_float(
        data.get(
            "current",
            existing["current"]
        )
    )

    deadline = data.get(
        "deadline",
        existing["deadline"]
    )

    if target is None or target <= 0:
        connection.close()
        return json_error(
            "Target must be greater than zero."
        )

    current = max(
        0,
        min(
            current,
            target
        )
    )

    if deadline:
        deadline = normalize_date(
            deadline
        )

    connection.execute(
        """
        UPDATE goals
        SET
            name = ?,
            target = ?,
            current = ?,
            deadline = ?
        WHERE id = ?
        """,
        (
            name,
            target,
            current,
            deadline,
            goal_id
        )
    )

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "message": "Goal updated."
    })


@app.route(
    "/api/goals/<int:goal_id>",
    methods=["DELETE"]
)
def delete_goal(goal_id):
    connection = get_db_connection()

    cursor = connection.execute(
        """
        DELETE FROM goals
        WHERE id = ?
        """,
        (goal_id,)
    )

    connection.commit()
    connection.close()

    if cursor.rowcount == 0:
        return json_error(
            "Goal not found.",
            404
        )

    return jsonify({
        "success": True,
        "message": "Goal deleted."
    })


# =========================================================
# GOAL PROGRESS
# =========================================================

@app.route("/api/goal-progress")
def goal_progress():
    connection = get_db_connection()

    goals = connection.execute(
        """
        SELECT *
        FROM goals
        ORDER BY id DESC
        """
    ).fetchall()

    connection.close()

    result = []

    for goal in goals:
        target = float(
            goal["target"] or 0
        )
        current = float(
            goal["current"] or 0
        )

        percentage = (
            (current / target) * 100
            if target > 0
            else 0
        )

        remaining = max(
            target - current,
            0
        )

        result.append({
            "id": goal["id"],
            "name": goal["name"],
            "target": round(
                target,
                2
            ),
            "current": round(
                current,
                2
            ),
            "remaining": round(
                remaining,
                2
            ),
            "percentage": round(
                percentage,
                2
            ),
            "deadline": goal["deadline"]
        })

    return jsonify(result)


# =========================================================
# RECURRING EXPENSES
# =========================================================

@app.route("/api/recurring")
def recurring():
    items = get_recurring_expenses()

    # Keep the original frontend-compatible fields while
    # adding useful new information.
    return jsonify(items)


@app.route("/api/recurring-expenses")
def recurring_expenses():
    items = get_recurring_expenses()

    return jsonify({
        "success": True,
        "recurring_expenses": items,
        "total_monthly": round(
            sum(
                item["estimated_monthly"]
                for item in items
            ),
            2
        )
    })


# =========================================================
# FINANCIAL HEALTH
# =========================================================

@app.route("/api/financial-health")
def financial_health():
    return jsonify(
        calculate_financial_health()
    )


# =========================================================
# BANK STATEMENT UPLOAD
# =========================================================

@app.errorhandler(413)
def request_entity_too_large(error):
    return json_error(
        f"File is too large. Maximum size is "
        f"{MAX_UPLOAD_MB} MB.",
        413
    )


def save_uploaded_file(file):
    original_name = os.path.basename(
        file.filename or ""
    )

    extension = os.path.splitext(
        original_name
    )[1].lower()

    if extension not in {".csv", ".pdf"}:
        raise ValueError(
            "Only PDF and CSV bank statements are supported."
        )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    safe_stem = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        os.path.splitext(original_name)[0]
    ).strip("_")

    if not safe_stem:
        safe_stem = "statement"

    filename = (
        f"{timestamp}_{safe_stem}{extension}"
    )

    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    file.save(filepath)

    return filepath, original_name, extension


def import_parsed_transactions(parsed_transactions):
    connection = get_db_connection()

    imported = 0
    duplicates = 0
    categorized = 0
    needs_review = 0
    skipped = 0

    for item in parsed_transactions:
        try:
            transaction_type = normalize_transaction_type(
                item.get("type")
            )

            amount = safe_float(
                item.get("amount")
            )

            transaction_date = normalize_date(
                item.get("date")
            )

            description = normalize_description(
                item.get("description")
            )

            category = canonical_category(
                item.get("category")
            )

            if not transaction_type:
                skipped += 1
                continue

            if amount is None or amount <= 0:
                skipped += 1
                continue

            if not transaction_date:
                skipped += 1
                continue

            if not description:
                description = "Bank transaction"

            if not category:
                category = categorize_transaction(
                    description,
                    transaction_type
                )

            if transaction_type == "income":
                category = (
                    "Salary"
                    if category == "Other"
                    else category
                )
            elif category == "Salary":
                category = "Other"

            inserted, _ = insert_transaction(
                connection,
                transaction_type,
                amount,
                category,
                description,
                transaction_date,
                skip_duplicate=True
            )

            if not inserted:
                duplicates += 1
                continue

            imported += 1

            if category == "Other":
                needs_review += 1
            else:
                categorized += 1

        except Exception:
            skipped += 1

    connection.commit()
    connection.close()

    return {
        "imported": imported,
        "duplicates": duplicates,
        "categorized": categorized,
        "needs_review": needs_review,
        "skipped": skipped
    }


@app.route(
    "/api/upload-statement",
    methods=["POST"]
)
def upload_statement():
    if "file" not in request.files:
        return json_error(
            "No file uploaded."
        )

    file = request.files["file"]

    if not file.filename:
        return json_error(
            "No file selected."
        )

    try:
        filepath, original_name, extension = (
            save_uploaded_file(file)
        )

        ai_used = False
        parsed_transactions = []

        if extension == ".csv":
            parsed_transactions = parse_csv_statement(
                filepath
            )

        elif extension == ".pdf":
            text = extract_pdf_text(
                filepath
            )

            if not text.strip():
                return json_error(
                    "This PDF does not contain readable text. "
                    "Scanned/image-only PDFs need OCR and are not "
                    "supported by this version."
                )

            # If AI is configured, let it interpret the PDF
            # because bank PDF layouts vary widely.
            if ai_is_configured():
                ai_transactions, ai_error = (
                    ai_parse_statement_text(text)
                )

                if ai_transactions is not None:
                    parsed_transactions = ai_transactions
                    ai_used = True
                else:
                    # Fall back to deterministic parsing.
                    parsed_transactions = (
                        parse_pdf_lines_heuristically(text)
                    )
            else:
                parsed_transactions = (
                    parse_pdf_lines_heuristically(text)
                )

        if not parsed_transactions:
            return json_error(
                "No reliable transactions could be extracted "
                "from this statement. Check the file format or "
                "configure the AI parser for complex PDF layouts.",
                400
            )

        result = import_parsed_transactions(
            parsed_transactions
        )

        return jsonify({
            "success": True,
            "message": (
                f"{result['imported']} transactions imported"
            ),
            "filename": original_name,
            "file_type": extension.replace(".", "").upper(),
            "ai_used": ai_used,
            **result
        })

    except ValueError as exc:
        return json_error(
            str(exc)
        )

    except RuntimeError as exc:
        return json_error(
            str(exc),
            500
        )

    except Exception as exc:
        app.logger.exception(
            "Statement import failed"
        )
        return json_error(
            f"Could not process the statement: {exc}",
            500
        )


# =========================================================
# AI STATUS
# =========================================================

@app.route("/api/ai-status")
def ai_status():
    return jsonify({
        "configured": ai_is_configured(),
        "model": AI_MODEL if ai_is_configured() else None
    })


# =========================================================
# SMART COACH AI CHAT
# =========================================================

@app.route(
    "/api/ai-chat",
    methods=["POST"]
)
def ai_chat():
    data = request.get_json(silent=True) or {}

    message = normalize_description(
        data.get("message")
    )

    if not message:
        return json_error(
            "Please enter a finance-related question."
        )

    result = ai_financial_answer(
        message
    )

    return jsonify(result)


# Alias for easier frontend integration.
@app.route(
    "/api/smart-coach",
    methods=["POST"]
)
def smart_coach():
    data = request.get_json(silent=True) or {}

    message = normalize_description(
        data.get("message")
        or data.get("question")
    )

    if not message:
        return json_error(
            "Please enter a finance-related question."
        )

    return jsonify(
        ai_financial_answer(message)
    )


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
        "message": "Database reset."
    })


# =========================================================
# APPLICATION START
# =========================================================

# Initialize immediately so API requests work even when the
# module is started through a WSGI server instead of __main__.
init_database()


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
