from flask import Flask, render_template, jsonify, request
import sqlite3
import pandas as pd
import os
from datetime import datetime, date
import json
import re
from collections import defaultdict

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from groq import Groq
except ImportError:
    Groq = None

try:
    import fitz  
except ImportError:
    fitz = None






app = Flask(__name__)

DATABASE = "finance.db"
UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
GROQ_WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo").strip()
MAX_UPLOAD_MB = 25
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

ALLOWED_STATEMENT_EXTENSIONS = {"csv", "pdf"}







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






def generate_insights():

    insights = []

    connection = get_db_connection()

    
    
    

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






def get_groq_client():
    """Return a Groq client when the SDK and API key are available."""
    if Groq is None:
        return None
    if not GROQ_API_KEY:
        return None
    return Groq(api_key=GROQ_API_KEY)


def ai_is_configured():
    
    
    
    return bool(GROQ_API_KEY)


def extract_json_from_text(text):
    """Safely extract a JSON object/array from an AI response."""
    if not text:
        return None
    text = str(text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.I | re.S)
    if fenced:
        try:
            return json.loads(fenced.group(1).strip())
        except json.JSONDecodeError:
            pass
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if not starts:
        return None
    start = min(starts)
    for end in range(len(text), start, -1):
        candidate = text[start:end].strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def groq_chat(messages, temperature=0.2, max_tokens=1200, json_mode=False):
    """Call Groq and return plain assistant text. Uses the SDK when available and a standard-library REST fallback otherwise."""
    if not GROQ_API_KEY:
        raise RuntimeError(
            "Groq AI is not configured. Set GROQ_API_KEY in .env."
        )

    
    client = get_groq_client()
    if client is not None:
        kwargs = {
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    
    
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    body = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}",
        },
        method="POST",
    )

    try:
        with urlrequest.urlopen(req, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            details = exc.read().decode("utf-8")
        except Exception:
            details = str(exc)
        raise RuntimeError(f"Groq API error: {details[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not connect to Groq: {exc}") from exc

    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("Groq returned no response choices.")

    message = choices[0].get("message") or {}
    content = message.get("content") or ""
    if isinstance(content, list):
        content = "".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict)
        )
    return str(content).strip()


def get_recurring_expenses_data():
    """Detect repeated expense descriptions and amounts."""
    connection = get_db_connection()
    rows = connection.execute("""
        SELECT
            LOWER(TRIM(description)) AS normalized_description,
            MIN(TRIM(description)) AS description,
            ROUND(amount, 2) AS amount,
            COUNT(*) AS occurrences,
            MIN(date) AS first_date,
            MAX(date) AS last_date
        FROM transactions
        WHERE type = 'expense'
          AND description IS NOT NULL
          AND TRIM(description) != ''
        GROUP BY LOWER(TRIM(description)), ROUND(amount, 2)
        HAVING COUNT(*) >= 3
        ORDER BY occurrences DESC, last_date DESC
    """).fetchall()
    connection.close()

    result = []
    for row in rows:
        result.append({
            "description": row["description"],
            "amount": round(float(row["amount"] or 0), 2),
            "occurrences": int(row["occurrences"] or 0),
            "first_date": row["first_date"],
            "last_date": row["last_date"],
            "estimated_monthly": round(float(row["amount"] or 0), 2),
        })
    return result


def format_ai_reply(text):
    """Clean an AI response so Smart Coach never shows raw markdown artifacts."""
    if not text:
        return "I could not generate a response right now."

    cleaned = str(text).strip()

    
    
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"__(.*?)__", r"\1", cleaned)
    cleaned = re.sub(r"(?<!\*)\*(?!\s)(.*?)(?<!\s)\*", r"\1", cleaned)
    cleaned = re.sub(r"`([^`]*)`", r"\1", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)

    lines = []
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
            continue

        
        line = re.sub(r"^#{1,6}\s*", "", line)

        
        line = re.sub(r"^[-*+]\s+", "• ", line)

        lines.append(line)

    cleaned = "\n".join(lines).strip()

    
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned


def get_ai_financial_context(limit=40):
    """Build compact structured financial context for Smart Coach."""
    summary = calculate_financial_summary()
    connection = get_db_connection()

    category_rows = connection.execute("""
        SELECT category, ROUND(SUM(amount), 2) AS total
        FROM transactions
        WHERE type = 'expense'
        GROUP BY category
        ORDER BY total DESC
    """).fetchall()

    recent_rows = connection.execute("""
        SELECT id, type, amount, category, description, date
        FROM transactions
        ORDER BY date DESC, id DESC
        LIMIT ?
    """, (limit,)).fetchall()

    budget_rows = connection.execute("""
        SELECT category, amount
        FROM budgets
        ORDER BY category
    """).fetchall()

    goal_rows = connection.execute("""
        SELECT id, name, target, current, deadline
        FROM goals
        ORDER BY id DESC
    """).fetchall()
    connection.close()

    return {
        "summary": summary,
        "spending_by_category": [
            {"category": r["category"], "amount": round(float(r["total"] or 0), 2)}
            for r in category_rows
        ],
        "budgets": [
            {"category": r["category"], "amount": round(float(r["amount"] or 0), 2)}
            for r in budget_rows
        ],
        "goals": [dict(r) for r in goal_rows],
        "recurring_expenses": get_recurring_expenses_data(),
        "recent_transactions": [
            {
                "id": r["id"],
                "type": r["type"],
                "amount": round(float(r["amount"] or 0), 2),
                "category": r["category"],
                "description": r["description"] or "",
                "date": r["date"],
            }
            for r in recent_rows
        ],
    }


def parse_statement_text_with_ai(text):
    """Turn extracted PDF text into normalized transactions using Groq."""
    if not text or not text.strip():
        return []

    
    text = text[:50000]
    system = """You are FinFlow's bank-statement parser. Extract only transaction rows from the supplied bank statement text.
Return JSON only in this exact shape: {"transactions":[{"date":"YYYY-MM-DD","description":"...","amount":123.45,"type":"income|expense"}]}
Rules: use positive numeric amounts; infer debit/credit from the statement wording or signs; ignore balances, headers, footers, page numbers and totals; never invent missing transactions; if a date is ambiguous, omit that row; normalize dates to YYYY-MM-DD where possible."""
    user = "Statement text:\n\n" + text
    raw = groq_chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0,
        max_tokens=6000,
        json_mode=True,
    )
    parsed = extract_json_from_text(raw) or {}
    transactions = parsed.get("transactions", []) if isinstance(parsed, dict) else []
    if not isinstance(transactions, list):
        return []
    return transactions


def normalize_ai_transactions(items):
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        transaction_type = normalize_transaction_type(item.get("type"))
        transaction_date = normalize_date(item.get("date"))
        description = str(item.get("description") or "").strip()
        try:
            amount = abs(float(item.get("amount")))
        except (TypeError, ValueError):
            continue
        if not transaction_type or not transaction_date or amount <= 0 or not description:
            continue
        normalized.append({
            "type": transaction_type,
            "amount": round(amount, 2),
            "description": description,
            "date": transaction_date,
            "category": categorize_transaction(description),
        })
    return normalized


def insert_transactions(items):
    """Insert normalized transaction dictionaries and return import statistics."""
    connection = get_db_connection()
    imported = categorized = needs_review = skipped = 0
    for item in items:
        try:
            category = item.get("category") or categorize_transaction(item.get("description", ""))
            if category not in CATEGORIES:
                category = "Other"
            if category == "Other":
                needs_review += 1
            else:
                categorized += 1
            connection.execute("""
                INSERT INTO transactions (type, amount, category, description, date)
                VALUES (?, ?, ?, ?, ?)
            """, (
                item["type"], item["amount"], category,
                item.get("description", ""), item["date"]
            ))
            imported += 1
        except Exception:
            skipped += 1
    connection.commit()
    connection.close()
    return {
        "imported": imported,
        "categorized": categorized,
        "needs_review": needs_review,
        "skipped": skipped,
    }


def extract_pdf_text(filepath):
    """Extract text from a text-based PDF. Scanned/image-only PDFs need OCR."""
    if fitz is None:
        raise RuntimeError("PDF support requires PyMuPDF. Run: pip install pymupdf")
    document = fitz.open(filepath)
    pages = []
    try:
        for page in document:
            pages.append(page.get_text("text"))
    finally:
        document.close()
    return "\n".join(pages).strip()


def parse_csv_dataframe(dataframe):
    """Normalize common bank CSV column names into FinFlow transactions."""
    normalized_columns = {str(c).strip().lower(): c for c in dataframe.columns}

    def find_column(*names):
        for name in names:
            if name in normalized_columns:
                return normalized_columns[name]
        return None

    date_col = find_column("date", "transaction date", "txn date", "value date")
    desc_col = find_column("description", "details", "narration", "remarks", "merchant", "transaction description")
    type_col = find_column("type", "transaction type", "dr/cr", "debit/credit")
    amount_col = find_column("amount", "transaction amount", "value")
    debit_col = find_column("debit", "withdrawal", "debit amount")
    credit_col = find_column("credit", "deposit", "credit amount")

    if not date_col or not desc_col:
        raise ValueError("CSV must contain a Date and Description/Details column.")
    if not amount_col and not debit_col and not credit_col:
        raise ValueError("CSV must contain Amount, Debit, or Credit columns.")

    result = []
    for _, row in dataframe.iterrows():
        try:
            description = str(row.get(desc_col, "") or "").strip()
            transaction_date = normalize_date(row.get(date_col))
            if not description or not transaction_date:
                continue

            transaction_type = normalize_transaction_type(row.get(type_col)) if type_col else None
            amount = None

            if amount_col:
                raw_amount = row.get(amount_col)
                amount = abs(float(raw_amount))
                if transaction_type is None:
                    
                    transaction_type = "expense" if float(raw_amount) < 0 else "income"
            else:
                debit = row.get(debit_col) if debit_col else None
                credit = row.get(credit_col) if credit_col else None
                debit_value = 0 if pd.isna(debit) else abs(float(str(debit).replace(",", "")))
                credit_value = 0 if pd.isna(credit) else abs(float(str(credit).replace(",", "")))
                if debit_value > 0:
                    amount, transaction_type = debit_value, "expense"
                elif credit_value > 0:
                    amount, transaction_type = credit_value, "income"

            if amount is None or amount <= 0 or not transaction_type:
                continue
            result.append({
                "type": transaction_type,
                "amount": round(amount, 2),
                "description": description,
                "date": transaction_date,
                "category": categorize_transaction(description),
            })
        except Exception:
            continue
    return result






@app.route("/api/ai/status")
def ai_status():
    configured = ai_is_configured()
    return jsonify({
        "configured": configured,
        "connected": configured,
        "status": "connected" if configured else "not_configured",
        "model": GROQ_MODEL if configured else None,
        "provider": "Groq" if configured else None,
    })


@app.route("/api/ai/test", methods=["GET", "POST"])
def ai_test():
    if not ai_is_configured():
        return jsonify({
            "success": False,
            "message": "Groq is not configured. Check GROQ_API_KEY in .env and install groq/python-dotenv."
        }), 503
    try:
        reply = groq_chat([
            {"role": "system", "content": "You are FinFlow's test assistant. Reply in one short sentence."},
            {"role": "user", "content": "Confirm that the FinFlow AI connection is working."},
        ], temperature=0, max_tokens=80)
        return jsonify({"success": True, "message": reply})
    except Exception as exc:
        return jsonify({"success": False, "message": f"Groq request failed: {exc}"}), 502


@app.route("/api/ai/chat", methods=["POST"])
def ai_chat():
    data = request.get_json(silent=True) or {}
    question = str(data.get("message") or data.get("question") or "").strip()
    if not question:
        return jsonify({"success": False, "message": "Please enter a finance question."}), 400
    if len(question) > 2000:
        return jsonify({"success": False, "message": "Question is too long."}), 400
    if not ai_is_configured():
        return jsonify({"success": False, "message": "Groq AI is not configured."}), 503

    context = get_ai_financial_context()
    system = """You are FinFlow Smart Coach, a personal finance assistant.
Answer only finance, budgeting, spending, saving, transaction, goal, or FinFlow-app questions.
If a request is unrelated, politely say you can help only with finance and FinFlow.
Use only the supplied financial context for personal financial facts. Never invent balances, transactions, budgets, goals, or spending numbers.
Give concise, practical answers in a natural human tone.
IMPORTANT RESPONSE FORMAT: Do not use Markdown syntax, asterisks, hashtags, code blocks, or markdown tables. Use plain text with clear short sections. When useful, structure the answer as:
Summary:
<one or two sentences>

Details:
• <fact>
• <fact>

Recommendation:
• <practical next step>
Only include sections that are useful for the question.
When making calculations, use the supplied numbers and show the calculation when useful. Format money with the ₹ symbol and commas, for example ₹1,500.00.
Do not claim to be a licensed financial adviser. For investments, taxes, loans, or other regulated matters, give general educational information and note when professional advice may be appropriate.
Financial context JSON follows:\n""" + json.dumps(context, ensure_ascii=False)

    try:
        reply = groq_chat([
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ], temperature=0.2, max_tokens=900)
        reply = format_ai_reply(reply)
        return jsonify({
            "success": True,
            "reply": reply,
            "answer": reply,
            "context_used": True,
            "ai_used": True
        })
    except Exception as exc:
        return jsonify({"success": False, "message": f"AI request failed: {exc}"}), 502



@app.route("/api/ai-status")
def ai_status_legacy():
    return ai_status()


@app.route("/api/ai-chat", methods=["POST"])
def ai_chat_legacy():
    return ai_chat()


@app.route("/api/ai/categorize", methods=["POST"])
def ai_categorize():
    data = request.get_json(silent=True) or {}
    descriptions = data.get("descriptions", [])
    if isinstance(descriptions, str):
        descriptions = [descriptions]
    descriptions = [str(x).strip() for x in descriptions if str(x).strip()][:100]
    if not descriptions:
        return jsonify({"success": False, "message": "No descriptions supplied."}), 400
    if not ai_is_configured():
        return jsonify({"success": False, "message": "Groq AI is not configured."}), 503

    prompt = "Return JSON only as {\"categories\":[{\"description\":\"...\",\"category\":\"Food|Transport|Shopping|Education|Bills|Entertainment|Health|Salary|Other\"}]} . Categorize each description conservatively. Descriptions:\n" + json.dumps(descriptions, ensure_ascii=False)
    try:
        raw = groq_chat([
            {"role": "system", "content": "You classify bank transaction descriptions into exactly one FinFlow category."},
            {"role": "user", "content": prompt},
        ], temperature=0, max_tokens=1600, json_mode=True)
        parsed = extract_json_from_text(raw) or {}
        categories = parsed.get("categories", []) if isinstance(parsed, dict) else []
        if not isinstance(categories, list):
            categories = []
        cleaned = []
        for item in categories:
            if not isinstance(item, dict):
                continue
            category = item.get("category", "Other")
            if category not in CATEGORIES:
                category = "Other"
            cleaned.append({"description": str(item.get("description", "")), "category": category})
        return jsonify({"success": True, "categories": cleaned})
    except Exception as exc:
        return jsonify({"success": False, "message": f"AI categorization failed: {exc}"}), 502


@app.route("/api/ai/transcribe", methods=["POST"])
def ai_transcribe():
    if not ai_is_configured():
        return jsonify({"success": False, "message": "Groq AI is not configured."}), 503
    if "file" not in request.files:
        return jsonify({"success": False, "message": "No audio file uploaded."}), 400
    audio = request.files["file"]
    if not audio.filename:
        return jsonify({"success": False, "message": "No audio file selected."}), 400
    client = get_groq_client()
    try:
        result = client.audio.transcriptions.create(
            file=(os.path.basename(audio.filename), audio.read()),
            model=GROQ_WHISPER_MODEL,
            response_format="json",
            temperature=0,
        )
        return jsonify({"success": True, "text": result.text})
    except Exception as exc:
        return jsonify({"success": False, "message": f"Voice transcription failed: {exc}"}), 502






@app.route("/")
def home():

    return render_template("index.html")


@app.route("/api/test")
def api_test():

    return jsonify({
        "message": "FinFlow backend connected",
        "status": "success"
    })






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






@app.route("/api/recurring")
def detect_recurring():
    recurring = get_recurring_expenses_data()
    return jsonify({
        "items": recurring,
        "count": len(recurring),
        "monthly_total": round(sum(item["estimated_monthly"] for item in recurring), 2),
    })






@app.route("/api/financial-health")
def financial_health():

    return jsonify(
        calculate_financial_health()
    )






@app.route(
    "/api/upload-statement",
    methods=["POST"]
)
def upload_statement():
    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file uploaded."}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"success": False, "message": "No file selected."}), 400

    extension = os.path.splitext(file.filename)[1].lower().lstrip(".")
    if extension not in ALLOWED_STATEMENT_EXTENSIONS:
        return jsonify({"success": False, "message": "Only CSV and PDF bank statements are supported."}), 400

    safe_filename = os.path.basename(file.filename)
    timestamped_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{safe_filename}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], timestamped_name)
    file.save(filepath)

    try:
        if extension == "csv":
            dataframe = pd.read_csv(filepath)
            transactions = parse_csv_dataframe(dataframe)
            stats = insert_transactions(transactions)
            stats.update({
                "success": True,
                "file_type": "csv",
                "message": f"{stats['imported']} transactions imported from CSV.",
            })
            return jsonify(stats)

        
        if not ai_is_configured():
            return jsonify({
                "success": False,
                "message": "PDF processing requires Groq AI. Check GROQ_API_KEY in .env."
            }), 503

        text = extract_pdf_text(filepath)
        if not text:
            return jsonify({
                "success": False,
                "message": "No readable text was found in this PDF. A scanned/image-only statement needs OCR before import."
            }), 400

        ai_transactions = parse_statement_text_with_ai(text)
        transactions = normalize_ai_transactions(ai_transactions)
        if not transactions:
            return jsonify({
                "success": False,
                "message": "The PDF was readable, but no transaction rows could be reliably extracted."
            }), 422

        stats = insert_transactions(transactions)
        stats.update({
            "success": True,
            "file_type": "pdf",
            "message": f"{stats['imported']} transactions imported from PDF using AI.",
        })
        return jsonify(stats)

    except pd.errors.EmptyDataError:
        return jsonify({"success": False, "message": "The CSV file is empty."}), 400
    except Exception as exc:
        return jsonify({"success": False, "message": f"Could not process statement: {exc}"}), 400
    finally:
        
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except OSError:
            pass






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






if __name__ == "__main__":

    init_database()

    app.run(
        debug=True
    )