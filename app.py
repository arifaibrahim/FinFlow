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







if __name__ == "__main__":

    init_database()

    app.run(debug=True)