"use strict";

/* =========================================================
   FINFLOW — MONEY IN MOTION
   Main Frontend JavaScript
   Works with Flask + SQLite backend
   ========================================================= */


/* =========================================================
   GLOBAL STATE
   ========================================================= */

const state = {
    currentPage: "home",

    transactions: [],
    budgets: [],
    goals: [],
    recurringExpenses: [],

    dashboard: null,

    transactionFilter: "all",
    transactionSearch: "",

    selectedStatementFile: null,

    charts: {
        incomeExpense: null,
        spending: null
    },

    isLoading: false
};


/* =========================================================
   DOM HELPERS
   ========================================================= */

function $(id) {
    return document.getElementById(id);
}

function $all(selector) {
    return document.querySelectorAll(selector);
}


/* =========================================================
   API HELPER
   ========================================================= */

async function fetchJSON(url, options = {}) {
    const response = await fetch(url, options);

    let data = {};

    try {
        data = await response.json();
    } catch (error) {
        throw new Error("The server returned an invalid response.");
    }

    if (!response.ok) {
        throw new Error(
            data.message ||
            data.error ||
            `Request failed with status ${response.status}`
        );
    }

    if (data.success === false) {
        throw new Error(data.message || data.error || "Request failed.");
    }

    return data;
}


/* =========================================================
   GENERAL UTILITIES
   ========================================================= */

function formatMoney(value) {
    const amount = Number(value) || 0;

    return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(amount);
}


function formatCompactMoney(value) {
    const amount = Number(value) || 0;

    if (Math.abs(amount) >= 10000000) {
        return `₹${(amount / 10000000).toFixed(1)}Cr`;
    }

    if (Math.abs(amount) >= 100000) {
        return `₹${(amount / 100000).toFixed(1)}L`;
    }

    if (Math.abs(amount) >= 1000) {
        return `₹${(amount / 1000).toFixed(1)}K`;
    }

    return formatMoney(amount);
}


function formatPercentage(value) {
    const number = Number(value);

    if (!Number.isFinite(number)) {
        return "0%";
    }

    return `${number.toFixed(1)}%`;
}


function formatChange(value) {
    const number = Number(value) || 0;

    if (number === 0) {
        return "0%";
    }

    const sign = number > 0 ? "+" : "";

    return `${sign}${number.toFixed(1)}%`;
}


function escapeHTML(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function getTodayString() {
    const today = new Date();

    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, "0");
    const day = String(today.getDate()).padStart(2, "0");

    return `${year}-${month}-${day}`;
}


function getCurrentYear() {
    return new Date().getFullYear();
}


function getCurrentMonth() {
    return new Date().getMonth() + 1;
}


function formatDate(dateString) {
    if (!dateString) {
        return "—";
    }

    const date = new Date(`${dateString}T00:00:00`);

    if (Number.isNaN(date.getTime())) {
        return dateString;
    }

    return date.toLocaleDateString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric"
    });
}


function debounce(callback, delay = 250) {
    let timeout;

    return (...args) => {
        clearTimeout(timeout);

        timeout = setTimeout(() => {
            callback(...args);
        }, delay);
    };
}


/* =========================================================
   TOAST NOTIFICATIONS
   ========================================================= */

function showToast(message, type = "success") {
    const toast = $("app-toast");

    if (!toast) {
        console.log(`[${type}] ${message}`);
        return;
    }

    toast.textContent = message;

    toast.classList.remove(
        "show",
        "success",
        "error",
        "warning",
        "info"
    );

    toast.classList.add(type);
    toast.classList.add("show");

    clearTimeout(showToast.timeout);

    showToast.timeout = setTimeout(() => {
        toast.classList.remove("show");
    }, 3200);
}


/* =========================================================
   MODAL MANAGEMENT
   ========================================================= */

function openModal(modalId) {
    const modal = $(modalId);

    if (!modal) {
        return;
    }

    modal.classList.add("active");
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
}


function closeModal(modalId) {
    const modal = $(modalId);

    if (!modal) {
        return;
    }

    modal.classList.remove("active");
    modal.setAttribute("aria-hidden", "true");

    if (!$(".modal.active")) {
        document.body.classList.remove("modal-open");
    }
}


function closeAllModals() {
    $all(".modal.active").forEach(modal => {
        modal.classList.remove("active");
        modal.setAttribute("aria-hidden", "true");
    });

    document.body.classList.remove("modal-open");
}


/* =========================================================
   PAGE NAVIGATION
   ========================================================= */

function showPage(pageName) {
    const page = pageName || "home";

    state.currentPage = page;

    $all(".page-view").forEach(view => {
        view.classList.remove("active");

        if (view.id === `${page}-view`) {
            view.classList.add("active");
        }
    });

    $all(".nav-item").forEach(item => {
        item.classList.remove("active");

        if (item.dataset.view === page) {
            item.classList.add("active");
        }
    });

    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });

    if (page === "home") {
        loadDashboard();
    }

    if (page === "transactions") {
        loadTransactions();
    }

    if (page === "budget") {
        loadBudgets();
        loadGoals();
    }

    if (page === "coach") {
        loadSmartCoach();
        loadRecurringExpenses();
        loadAIStatus();
    }
}


/* =========================================================
   NAVIGATION EVENTS
   ========================================================= */

function setupNavigation() {
    $all(".nav-item").forEach(button => {
        button.addEventListener("click", () => {
            const page = button.dataset.view;

            if (page) {
                showPage(page);
            }
        });
    });

    $all("[data-open-page]").forEach(element => {
        element.addEventListener("click", event => {
            event.preventDefault();

            const page = element.dataset.openPage;

            if (page) {
                showPage(page);
            }
        });
    });
}


/* =========================================================
   SUMMARY / DASHBOARD
   ========================================================= */

async function loadDashboard() {
    try {
        const data = await fetchJSON("/api/dashboard");

        state.dashboard = data;

        renderDashboardSummary(data.summary || {});
        renderHomeInsights(data.insights || []);
        renderHomeRecurring(data.recurring_expenses || []);
        renderFinancialHealth(data.health || {});
        renderHomeBudgetProgress();

        await loadHomeCharts();

    } catch (error) {
        console.error("Dashboard error:", error);

        showToast(
            `Unable to load dashboard: ${error.message}`,
            "error"
        );
    }
}


function renderDashboardSummary(summary) {
    const income = Number(summary.income) || 0;
    const expenses = Number(summary.expenses) || 0;
    const balance = Number(summary.balance) || 0;
    const savingsRate = Number(summary.savings_rate) || 0;

    if ($("balance-value")) {
        $("balance-value").textContent = formatMoney(balance);
    }

    if ($("income-value")) {
        $("income-value").textContent = formatMoney(income);
    }

    if ($("expense-value")) {
        $("expense-value").textContent = formatMoney(expenses);
    }

    if ($("savings-value")) {
        $("savings-value").textContent = formatPercentage(savingsRate);
    }

    const changes = summary.changes || {};

    setChangeText(
        "balance-change",
        changes.balance
    );

    setChangeText(
        "income-change",
        changes.income
    );

    setChangeText(
        "expense-change",
        changes.expenses
    );

    setChangeText(
        "savings-change",
        changes.savings_rate
    );
}


function setChangeText(elementId, value) {
    const element = $(elementId);

    if (!element) {
        return;
    }

    const number = Number(value) || 0;

    element.textContent = `${formatChange(number)} from last month`;

    element.classList.remove("positive", "negative", "neutral");

    if (number > 0) {
        element.classList.add("positive");
    } else if (number < 0) {
        element.classList.add("negative");
    } else {
        element.classList.add("neutral");
    }
}


/* =========================================================
   HOME INSIGHTS
   ========================================================= */

function renderHomeInsights(insights) {
    const container = $("home-insights");

    if (!container) {
        return;
    }

    if (!Array.isArray(insights) || insights.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No financial insights available yet.</p>
            </div>
        `;

        return;
    }

    container.innerHTML = insights
        .slice(0, 6)
        .map((insight, index) => {
            let title = "Financial Insight";
            let text = "";
            let icon = "💡";

            if (typeof insight === "string") {
                text = insight;
            } else {
                title =
                    insight.title ||
                    insight.heading ||
                    insight.type ||
                    "Financial Insight";

                text =
                    insight.message ||
                    insight.description ||
                    insight.text ||
                    "";

                icon =
                    insight.icon ||
                    ["💡", "📊", "🎯", "💰", "⚡", "📈"][index % 6];
            }

            return `
                <div class="insight-card">
                    <div class="insight-icon">${escapeHTML(icon)}</div>
                    <div class="insight-content">
                        <h4>${escapeHTML(title)}</h4>
                        <p>${escapeHTML(text)}</p>
                    </div>
                </div>
            `;
        })
        .join("");
}


/* =========================================================
   HOME BUDGET PREVIEW
   ========================================================= */

async function renderHomeBudgetProgress() {
    const container = $("home-budget-progress");

    if (!container) {
        return;
    }

    try {
        const year = getCurrentYear();
        const month = getCurrentMonth();

        const data = await fetchJSON(
            `/api/budget-progress?year=${year}&month=${month}`
        );

        const budgets = Array.isArray(data)
            ? data
            : data.budgets || [];

        if (budgets.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>No budgets created yet.</p>
                    <button
                        class="btn btn-secondary"
                        type="button"
                        data-open-page="budget"
                    >
                        Create Budget
                    </button>
                </div>
            `;

            const button = container.querySelector("[data-open-page]");

            if (button) {
                button.addEventListener("click", () => {
                    showPage("budget");
                });
            }

            return;
        }

        container.innerHTML = budgets
            .slice(0, 5)
            .map(renderBudgetProgressItem)
            .join("");

    } catch (error) {
        console.error("Home budget progress error:", error);

        container.innerHTML = `
            <div class="empty-state">
                <p>Budget progress unavailable.</p>
            </div>
        `;
    }
}


function renderBudgetProgressItem(item) {
    const category = item.category || "Other";
    const budget = Number(item.budget) || 0;
    const spent = Number(item.spent) || 0;

    let percentage = Number(item.percentage);

    if (!Number.isFinite(percentage)) {
        percentage = budget > 0
            ? (spent / budget) * 100
            : 0;
    }

    percentage = Math.max(0, Math.min(100, percentage));

    const remaining = Math.max(0, budget - spent);

    let statusClass = "safe";

    if (percentage >= 100) {
        statusClass = "danger";
    } else if (percentage >= 80) {
        statusClass = "warning";
    }

    return `
        <div class="budget-progress-item">
            <div class="budget-progress-header">
                <span>${escapeHTML(category)}</span>
                <strong>${formatMoney(spent)} / ${formatMoney(budget)}</strong>
            </div>

            <div class="progress-track">
                <div
                    class="progress-fill ${statusClass}"
                    style="width:${percentage}%"
                ></div>
            </div>

            <div class="budget-progress-footer">
                <span>${percentage.toFixed(0)}% used</span>
                <span>${formatMoney(remaining)} remaining</span>
            </div>
        </div>
    `;
}


/* =========================================================
   HOME RECURRING PREVIEW
   ========================================================= */

function renderHomeRecurring(recurring) {
    const container = $("home-recurring-list");

    if (!container) {
        return;
    }

    if (!Array.isArray(recurring) || recurring.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No recurring expenses detected yet.</p>
            </div>
        `;

        return;
    }

    container.innerHTML = recurring
        .slice(0, 4)
        .map(item => `
            <div class="recurring-item">
                <div class="recurring-info">
                    <strong>${escapeHTML(
                        item.description || "Recurring expense"
                    )}</strong>

                    <span>
                        ${escapeHTML(item.category || "Other")}
                        ·
                        ${escapeHTML(item.frequency || "Recurring")}
                    </span>
                </div>

                <div class="recurring-amount">
                    ${formatMoney(item.amount)}
                </div>
            </div>
        `)
        .join("");
}


/* =========================================================
   CHARTS
   ========================================================= */

async function loadHomeCharts() {
    if (typeof Chart === "undefined") {
        console.warn("Chart.js is not loaded.");
        return;
    }

    await Promise.allSettled([
        loadIncomeExpenseChart(),
        loadSpendingChart()
    ]);
}


async function loadIncomeExpenseChart() {
    const canvas = $("income-expense-chart");

    if (!canvas) {
        return;
    }

    const yearSelector = $("cashflow-year");
    const monthSelector = $("cashflow-month");

    const year = yearSelector
        ? yearSelector.value || getCurrentYear()
        : getCurrentYear();

    const month = monthSelector
        ? monthSelector.value
        : "";

    let url = `/api/monthly-summary?year=${year}`;

    if (month && month !== "all") {
        url += `&month=${month}`;
    }

    try {
        const data = await fetchJSON(url);

        let months = Array.isArray(data)
            ? data
            : data.months || [];

        if (month && month !== "all" && months.length === 1) {
            months = months;
        }

        const labels = months.map(item => {
            if (item.month_name) {
                return item.month_name;
            }

            return new Date(
                Number(item.year || year),
                Number(item.month || 1) - 1,
                1
            ).toLocaleDateString("en-IN", {
                month: "short"
            });
        });

        const income = months.map(item =>
            Number(item.income) || 0
        );

        const expenses = months.map(item =>
            Number(item.expenses) || 0
        );

        if (state.charts.incomeExpense) {
            state.charts.incomeExpense.destroy();
        }

        state.charts.incomeExpense = new Chart(
            canvas.getContext("2d"),
            {
                type: "bar",

                data: {
                    labels,

                    datasets: [
                        {
                            label: "Income",
                            data: income,
                            borderWidth: 1,
                            borderRadius: 6
                        },
                        {
                            label: "Expenses",
                            data: expenses,
                            borderWidth: 1,
                            borderRadius: 6
                        }
                    ]
                },

                options: {
                    responsive: true,
                    maintainAspectRatio: false,

                    interaction: {
                        mode: "index",
                        intersect: false
                    },

                    plugins: {
                        legend: {
                            display: true
                        },

                        tooltip: {
                            callbacks: {
                                label(context) {
                                    return `${context.dataset.label}: ${formatMoney(
                                        context.raw
                                    )}`;
                                }
                            }
                        }
                    },

                    scales: {
                        y: {
                            beginAtZero: true,

                            ticks: {
                                callback(value) {
                                    return formatCompactMoney(value);
                                }
                            }
                        }
                    }
                }
            }
        );

    } catch (error) {
        console.error("Income/expense chart error:", error);
    }
}


async function loadSpendingChart() {
    const canvas = $("spending-chart");

    if (!canvas) {
        return;
    }

    const yearSelector = $("spending-year");
    const monthSelector = $("spending-month");

    const year = yearSelector
        ? yearSelector.value || getCurrentYear()
        : getCurrentYear();

    const month = monthSelector
        ? monthSelector.value
        : "";

    let url = `/api/spending-by-category?year=${year}`;

    if (month && month !== "all") {
        url += `&month=${month}`;
    }

    try {
        const data = await fetchJSON(url);

        const categories = Array.isArray(data)
            ? data
            : data.categories || [];

        const labels = categories.map(item =>
            item.category || "Other"
        );

        const values = categories.map(item =>
            Number(item.total) || 0
        );

        const total = values.reduce(
            (sum, value) => sum + value,
            0
        );

        if ($("spending-total")) {
            $("spending-total").textContent =
                formatMoney(total);
        }

        if (state.charts.spending) {
            state.charts.spending.destroy();
        }

        state.charts.spending = new Chart(
            canvas.getContext("2d"),
            {
                type: "doughnut",

                data: {
                    labels,

                    datasets: [
                        {
                            data: values,
                            borderWidth: 2
                        }
                    ]
                },

                options: {
                    responsive: true,
                    maintainAspectRatio: false,

                    plugins: {
                        legend: {
                            position: "bottom"
                        },

                        tooltip: {
                            callbacks: {
                                label(context) {
                                    const value =
                                        Number(context.raw) || 0;

                                    const percentage =
                                        total > 0
                                            ? (value / total) * 100
                                            : 0;

                                    return `${context.label}: ${formatMoney(
                                        value
                                    )} (${percentage.toFixed(1)}%)`;
                                }
                            }
                        }
                    }
                }
            }
        );

    } catch (error) {
        console.error("Spending chart error:", error);
    }
}


/* =========================================================
   CHART FILTERS
   ========================================================= */

function setupChartFilters() {
    const cashflowMonth = $("cashflow-month");
    const cashflowYear = $("cashflow-year");

    if (cashflowMonth) {
        cashflowMonth.addEventListener(
            "change",
            loadIncomeExpenseChart
        );
    }

    if (cashflowYear) {
        cashflowYear.addEventListener(
            "change",
            loadIncomeExpenseChart
        );
    }

    const spendingMonth = $("spending-month");
    const spendingYear = $("spending-year");

    if (spendingMonth) {
        spendingMonth.addEventListener(
            "change",
            loadSpendingChart
        );
    }

    if (spendingYear) {
        spendingYear.addEventListener(
            "change",
            loadSpendingChart
        );
    }
}


/* =========================================================
   YEAR SELECTORS
   ========================================================= */

function populateYearSelectors() {
    const currentYear = getCurrentYear();

    const selectors = [
        $("cashflow-year"),
        $("spending-year")
    ].filter(Boolean);

    selectors.forEach(select => {
        const existingValue = select.value;

        select.innerHTML = "";

        for (
            let year = currentYear - 4;
            year <= currentYear;
            year++
        ) {
            const option = document.createElement("option");

            option.value = year;
            option.textContent = year;

            select.appendChild(option);
        }

        select.value = existingValue || currentYear;
    });
}


function setCurrentMonthSelectors() {
    const currentMonth = getCurrentMonth();

    [
        $("cashflow-month"),
        $("spending-month")
    ].filter(Boolean).forEach(select => {
        if (
            !select.value ||
            select.value === ""
        ) {
            select.value = "all";
        }
    });

    return currentMonth;
}


/* =========================================================
   TRANSACTIONS
   ========================================================= */

async function loadTransactions() {
    try {
        const data = await fetchJSON("/api/transactions");

        state.transactions = Array.isArray(data)
            ? data
            : data.transactions || [];

        renderTransactions();

    } catch (error) {
        console.error("Transactions error:", error);

        showToast(
            `Unable to load transactions: ${error.message}`,
            "error"
        );
    }
}


function renderTransactions() {
    const tableBody = $("transaction-table-body");

    if (!tableBody) {
        return;
    }

    let transactions = [...state.transactions];

    if (state.transactionFilter !== "all") {
        transactions = transactions.filter(
            transaction =>
                String(transaction.type || "").toLowerCase() ===
                state.transactionFilter
        );
    }

    const search = state.transactionSearch
        .trim()
        .toLowerCase();

    if (search) {
        transactions = transactions.filter(transaction => {
            const searchableText = [
                transaction.description,
                transaction.category,
                transaction.date,
                transaction.type
            ]
                .filter(Boolean)
                .join(" ")
                .toLowerCase();

            return searchableText.includes(search);
        });
    }

    transactions.sort((a, b) => {
        return String(b.date || "").localeCompare(
            String(a.date || "")
        );
    });

    if ($("transaction-count")) {
        $("transaction-count").textContent =
            `${transactions.length} transaction${
                transactions.length === 1 ? "" : "s"
            }`;
    }

    if (transactions.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="5">
                    <div class="empty-state">
                        <p>No transactions found.</p>
                    </div>
                </td>
            </tr>
        `;

        return;
    }

    tableBody.innerHTML = transactions
        .map(transaction => {
            const type =
                String(transaction.type || "expense")
                    .toLowerCase();

            const isIncome = type === "income";

            const amount = Number(transaction.amount) || 0;

            return `
                <tr data-transaction-id="${transaction.id}">
                    <td>
                        ${escapeHTML(formatDate(transaction.date))}
                    </td>

                    <td>
                        <div class="transaction-description">
                            <strong>
                                ${escapeHTML(
                                    transaction.description ||
                                    "Transaction"
                                )}
                            </strong>

                            <button
                                type="button"
                                class="transaction-delete-btn"
                                data-delete-transaction="${transaction.id}"
                                title="Delete transaction"
                                aria-label="Delete transaction"
                            >
                                ×
                            </button>
                        </div>
                    </td>

                    <td>
                        <span class="category-badge">
                            ${escapeHTML(
                                transaction.category || "Other"
                            )}
                        </span>
                    </td>

                    <td>
                        <span class="transaction-type ${isIncome
                            ? "income"
                            : "expense"}">
                            ${isIncome ? "Income" : "Expense"}
                        </span>
                    </td>

                    <td class="${isIncome
                        ? "amount-income"
                        : "amount-expense"}">
                        ${isIncome ? "+" : "-"}${formatMoney(amount)}
                    </td>
                </tr>
            `;
        })
        .join("");

    $all("[data-delete-transaction]").forEach(button => {
        button.addEventListener("click", async () => {
            const id = button.dataset.deleteTransaction;

            await deleteTransaction(id);
        });
    });
}


async function deleteTransaction(id) {
    if (!id) {
        return;
    }

    const transaction = state.transactions.find(
        item => String(item.id) === String(id)
    );

    const description =
        transaction?.description || "this transaction";

    const confirmed = window.confirm(
        `Delete ${description}?`
    );

    if (!confirmed) {
        return;
    }

    try {
        await fetchJSON(`/api/transactions/${id}`, {
            method: "DELETE"
        });

        showToast("Transaction deleted.", "success");

        await refreshAll();

    } catch (error) {
        console.error("Delete transaction error:", error);

        showToast(
            `Could not delete transaction: ${error.message}`,
            "error"
        );
    }
}


/* =========================================================
   TRANSACTION FILTERS
   ========================================================= */

function setupTransactionFilters() {
    $all(".filter-tab").forEach(tab => {
        tab.addEventListener("click", () => {
            $all(".filter-tab").forEach(item => {
                item.classList.remove("active");
            });

            tab.classList.add("active");

            state.transactionFilter =
                tab.dataset.filter || "all";

            renderTransactions();
        });
    });

    const search = $("transaction-search");

    if (search) {
        search.addEventListener(
            "input",
            debounce(event => {
                state.transactionSearch =
                    event.target.value || "";

                renderTransactions();
            }, 200)
        );
    }
}


/* =========================================================
   TRANSACTION FORM
   ========================================================= */

function setupTransactionForm() {
    const form = $("transaction-form");

    if (!form) {
        return;
    }

    const dateInput = $("transaction-date");

    if (
        dateInput &&
        !dateInput.value
    ) {
        dateInput.value = getTodayString();
    }

    form.addEventListener("submit", async event => {
        event.preventDefault();

        const type =
            $("transaction-type")?.value || "expense";

        const amount =
            Number($("transaction-amount")?.value || 0);

        const category =
            $("transaction-category")?.value || "Other";

        const description =
            $("transaction-description")?.value.trim() || "";

        const date =
            $("transaction-date")?.value || getTodayString();

        if (!amount || amount <= 0) {
            showToast(
                "Please enter a valid amount.",
                "warning"
            );

            return;
        }

        if (!description) {
            showToast(
                "Please enter a description.",
                "warning"
            );

            return;
        }

        try {
            await fetchJSON("/api/transactions", {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    type,
                    amount,
                    category,
                    description,
                    date
                })
            });

            showToast(
                "Transaction added successfully.",
                "success"
            );

            form.reset();

            if ($("transaction-date")) {
                $("transaction-date").value =
                    getTodayString();
            }

            closeModal("transaction-modal");

            await refreshAll();

        } catch (error) {
            console.error("Add transaction error:", error);

            showToast(
                `Could not add transaction: ${error.message}`,
                "error"
            );
        }
    });
}


/* =========================================================
   TRANSACTION CATEGORY AUTO-CATEGORIZATION
   ========================================================= */

function setupCategorySuggestion() {
    const descriptionInput =
        $("transaction-description");

    const typeInput =
        $("transaction-type");

    if (!descriptionInput) {
        return;
    }

    const suggestCategory = debounce(async () => {
        const description =
            descriptionInput.value.trim();

        if (!description || !typeInput) {
            return;
        }

        try {
            const data = await fetchJSON(
                "/api/categorize",
                {
                    method: "POST",

                    headers: {
                        "Content-Type": "application/json"
                    },

                    body: JSON.stringify({
                        description,
                        type: typeInput.value
                    })
                }
            );

            if (
                data.category &&
                $("transaction-category")
            ) {
                $("transaction-category").value =
                    data.category;
            }

        } catch (error) {
            console.debug(
                "Category suggestion unavailable:",
                error
            );
        }
    }, 500);

    descriptionInput.addEventListener(
        "input",
        suggestCategory
    );
}


/* =========================================================
   STATEMENT UPLOAD
   ========================================================= */

function setupStatementUpload() {
    const openButton =
        $("upload-statement-btn");

    const fileInput =
        $("statement-file");

    const chooseButton =
        $("choose-statement-btn");

    const importButton =
        $("import-statement-btn");

    const dropZone =
        $("statement-drop-zone");

    if (openButton) {
        openButton.addEventListener("click", () => {
            state.selectedStatementFile = null;

            if (fileInput) {
                fileInput.value = "";
            }

            updateSelectedStatementName();

            if ($("upload-result")) {
                $("upload-result").textContent = "";
            }

            openModal("upload-modal");
        });
    }

    if (chooseButton && fileInput) {
        chooseButton.addEventListener("click", event => {
            event.preventDefault();
            fileInput.click();
        });
    }

    if (fileInput) {
        fileInput.addEventListener("change", () => {
            const file = fileInput.files?.[0];

            if (file) {
                selectStatementFile(file);
            }
        });
    }

    if (dropZone) {
        [
            "dragenter",
            "dragover"
        ].forEach(eventName => {
            dropZone.addEventListener(
                eventName,
                event => {
                    event.preventDefault();
                    event.stopPropagation();

                    dropZone.classList.add("drag-over");
                }
            );
        });

        [
            "dragleave",
            "drop"
        ].forEach(eventName => {
            dropZone.addEventListener(
                eventName,
                event => {
                    event.preventDefault();
                    event.stopPropagation();

                    dropZone.classList.remove(
                        "drag-over"
                    );
                }
            );
        });

        dropZone.addEventListener(
            "drop",
            event => {
                const file =
                    event.dataTransfer?.files?.[0];

                if (file) {
                    selectStatementFile(file);
                }
            }
        );
    }

    if (importButton) {
        importButton.addEventListener(
            "click",
            importStatement
        );
    }
}


function selectStatementFile(file) {
    const allowedExtensions = [
        ".csv",
        ".pdf"
    ];

    const filename =
        String(file.name || "").toLowerCase();

    const isAllowed =
        allowedExtensions.some(
            extension =>
                filename.endsWith(extension)
        );

    if (!isAllowed) {
        showToast(
            "Please select a CSV or PDF statement.",
            "warning"
        );

        return;
    }

    state.selectedStatementFile = file;

    updateSelectedStatementName();

    showToast(
        `${file.name} selected.`,
        "info"
    );
}


function updateSelectedStatementName() {
    const element =
        $("selected-statement-name");

    if (!element) {
        return;
    }

    if (state.selectedStatementFile) {
        element.textContent =
            state.selectedStatementFile.name;
    } else {
        element.textContent =
            "No file selected";
    }
}


async function importStatement() {
    const file =
        state.selectedStatementFile;

    if (!file) {
        showToast(
            "Please select a CSV or PDF file first.",
            "warning"
        );

        return;
    }

    const button =
        $("import-statement-btn");

    if (button) {
        button.disabled = true;
        button.textContent = "Importing...";
    }

    try {
        const formData = new FormData();

        formData.append("file", file);

        const data = await fetchJSON(
            "/api/upload-statement",
            {
                method: "POST",
                body: formData
            }
        );

        const imported =
            Number(data.imported) || 0;

        const duplicates =
            Number(data.duplicates) || 0;

        const needsReview =
            Number(data.needs_review) || 0;

        const message =
            data.message ||
            `Imported ${imported} transaction${
                imported === 1 ? "" : "s"
            }.`;

        if ($("upload-result")) {
            $("upload-result").innerHTML = `
                <strong>Import complete</strong>
                <p>${escapeHTML(message)}</p>
                <small>
                    Imported: ${imported}
                    · Duplicates: ${duplicates}
                    · Review: ${needsReview}
                </small>
            `;
        }

        showToast(
            message,
            "success"
        );

        state.selectedStatementFile = null;

        if ($("statement-file")) {
            $("statement-file").value = "";
        }

        updateSelectedStatementName();

        await refreshAll();

    } catch (error) {
        console.error("Statement upload error:", error);

        if ($("upload-result")) {
            $("upload-result").innerHTML = `
                <div class="upload-error">
                    ${escapeHTML(error.message)}
                </div>
            `;
        }

        showToast(
            `Import failed: ${error.message}`,
            "error"
        );

    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = "Import Statement";
        }
    }
}


/* =========================================================
   BUDGETS
   ========================================================= */

async function loadBudgets() {
    try {
        const data = await fetchJSON("/api/budgets");

        state.budgets = Array.isArray(data)
            ? data
            : data.budgets || [];

        await renderBudgets();

    } catch (error) {
        console.error("Budget error:", error);

        showToast(
            `Unable to load budgets: ${error.message}`,
            "error"
        );
    }
}


async function renderBudgets() {
    const container = $("budget-list");

    if (!container) {
        return;
    }

    if (state.budgets.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">💰</div>
                <h3>No budgets yet</h3>
                <p>
                    Create your first category budget
                    to start tracking your spending.
                </p>

                <button
                    type="button"
                    class="btn btn-primary"
                    id="empty-create-budget-btn-inner"
                >
                    Create Budget
                </button>
            </div>
        `;

        const button =
            $("empty-create-budget-btn-inner");

        if (button) {
            button.addEventListener(
                "click",
                () => openModal("budget-modal")
            );
        }

        return;
    }

    try {
        const year = getCurrentYear();
        const month = getCurrentMonth();

        const data = await fetchJSON(
            `/api/budget-progress?year=${year}&month=${month}`
        );

        const progress = Array.isArray(data)
            ? data
            : data.budgets || [];

        const progressMap = new Map(
            progress.map(item => [
                String(item.category),
                item
            ])
        );

        container.innerHTML = state.budgets
            .map(budget => {
                const category =
                    budget.category || "Other";

                const amount =
                    Number(budget.amount) || 0;

                const item =
                    progressMap.get(
                        String(category)
                    );

                const spent =
                    Number(item?.spent) || 0;

                let percentage =
                    Number(item?.percentage);

                if (!Number.isFinite(percentage)) {
                    percentage =
                        amount > 0
                            ? (spent / amount) * 100
                            : 0;
                }

                const safePercentage =
                    Math.max(
                        0,
                        Math.min(100, percentage)
                    );

                const remaining =
                    Math.max(
                        0,
                        amount - spent
                    );

                let statusClass = "safe";

                if (percentage >= 100) {
                    statusClass = "danger";
                } else if (percentage >= 80) {
                    statusClass = "warning";
                }

                return `
                    <div
                        class="budget-card ${statusClass}"
                        data-budget-id="${budget.id}"
                    >
                        <div class="budget-card-header">
                            <div>
                                <span class="budget-category">
                                    ${escapeHTML(category)}
                                </span>

                                <h3>
                                    ${formatMoney(amount)}
                                </h3>
                            </div>

                            <button
                                type="button"
                                class="delete-budget-btn"
                                data-delete-budget="${budget.id}"
                                title="Delete budget"
                            >
                                ×
                            </button>
                        </div>

                        <div class="budget-spending">
                            <span>
                                Spent
                                <strong>
                                    ${formatMoney(spent)}
                                </strong>
                            </span>

                            <span>
                                ${percentage.toFixed(0)}%
                            </span>
                        </div>

                        <div class="progress-track">
                            <div
                                class="progress-fill ${statusClass}"
                                style="width:${safePercentage}%"
                            ></div>
                        </div>

                        <div class="budget-card-footer">
                            <span>
                                ${formatMoney(remaining)}
                                remaining
                            </span>

                            <span>
                                ${percentage >= 100
                                    ? "Over budget"
                                    : "Within budget"}
                            </span>
                        </div>
                    </div>
                `;
            })
            .join("");

        $all("[data-delete-budget]").forEach(
            button => {
                button.addEventListener(
                    "click",
                    async () => {
                        await deleteBudget(
                            button.dataset.deleteBudget
                        );
                    }
                );
            }
        );

    } catch (error) {
        console.error(
            "Budget progress error:",
            error
        );

        container.innerHTML =
            state.budgets
                .map(budget => `
                    <div class="budget-card">
                        <div class="budget-card-header">
                            <div>
                                <span class="budget-category">
                                    ${escapeHTML(
                                        budget.category
                                    )}
                                </span>

                                <h3>
                                    ${formatMoney(
                                        budget.amount
                                    )}
                                </h3>
                            </div>

                            <button
                                type="button"
                                class="delete-budget-btn"
                                data-delete-budget="${budget.id}"
                            >
                                ×
                            </button>
                        </div>
                    </div>
                `)
                .join("");

        $all("[data-delete-budget]").forEach(
            button => {
                button.addEventListener(
                    "click",
                    async () => {
                        await deleteBudget(
                            button.dataset.deleteBudget
                        );
                    }
                );
            }
        );
    }
}


function setupBudgetForm() {
    const form = $("budget-form");

    if (!form) {
        return;
    }

    form.addEventListener("submit", async event => {
        event.preventDefault();

        const category =
            $("budget-category")?.value || "";

        const amount =
            Number($("budget-amount")?.value || 0);

        if (!category) {
            showToast(
                "Please select a category.",
                "warning"
            );

            return;
        }

        if (!amount || amount <= 0) {
            showToast(
                "Please enter a valid budget amount.",
                "warning"
            );

            return;
        }

        try {
            await fetchJSON("/api/budgets", {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    category,
                    amount
                })
            });

            showToast(
                "Budget created successfully.",
                "success"
            );

            form.reset();

            closeModal("budget-modal");

            await refreshAll();

            showPage("budget");

        } catch (error) {
            console.error(
                "Create budget error:",
                error
            );

            showToast(
                `Could not create budget: ${error.message}`,
                "error"
            );
        }
    });
}


async function deleteBudget(id) {
    if (!id) {
        return;
    }

    const confirmed = window.confirm(
        "Delete this budget?"
    );

    if (!confirmed) {
        return;
    }

    try {
        await fetchJSON(`/api/budgets/${id}`, {
            method: "DELETE"
        });

        showToast(
            "Budget deleted.",
            "success"
        );

        await refreshAll();

    } catch (error) {
        console.error(
            "Delete budget error:",
            error
        );

        showToast(
            `Could not delete budget: ${error.message}`,
            "error"
        );
    }
}


/* =========================================================
   GOALS
   ========================================================= */

async function loadGoals() {
    try {
        const data =
            await fetchJSON("/api/goal-progress");

        state.goals = Array.isArray(data)
            ? data
            : data.goals || [];

        renderGoals();

    } catch (error) {
        console.error("Goals error:", error);

        showToast(
            `Unable to load goals: ${error.message}`,
            "error"
        );
    }
}


function renderGoals() {
    const container = $("goals-list");

    if (!container) {
        return;
    }

    if (state.goals.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🎯</div>
                <h3>No goals yet</h3>
                <p>
                    Set a financial goal and track your
                    progress over time.
                </p>

                <button
                    type="button"
                    class="btn btn-primary"
                    id="empty-create-goal-btn-inner"
                >
                    Create Goal
                </button>
            </div>
        `;

        const button =
            $("empty-create-goal-btn-inner");

        if (button) {
            button.addEventListener(
                "click",
                () => openModal("goal-modal")
            );
        }

        return;
    }

    container.innerHTML = state.goals
        .map(goal => {
            const target =
                Number(goal.target) || 0;

            const current =
                Number(goal.current) || 0;

            let percentage =
                Number(goal.percentage);

            if (!Number.isFinite(percentage)) {
                percentage =
                    target > 0
                        ? (current / target) * 100
                        : 0;
            }

            const safePercentage =
                Math.max(
                    0,
                    Math.min(100, percentage)
                );

            const remaining =
                Math.max(
                    0,
                    Number(goal.remaining) ||
                    (target - current)
                );

            return `
                <div
                    class="goal-card"
                    data-goal-id="${goal.id}"
                >
                    <div class="goal-card-header">
                        <div>
                            <span class="goal-icon">
                                🎯
                            </span>

                            <h3>
                                ${escapeHTML(
                                    goal.name ||
                                    "Financial Goal"
                                )}
                            </h3>
                        </div>

                        <button
                            type="button"
                            class="delete-goal-btn"
                            data-delete-goal="${goal.id}"
                            title="Delete goal"
                        >
                            ×
                        </button>
                    </div>

                    <div class="goal-values">
                        <strong>
                            ${formatMoney(current)}
                        </strong>

                        <span>
                            of ${formatMoney(target)}
                        </span>
                    </div>

                    <div class="progress-track">
                        <div
                            class="progress-fill"
                            style="width:${safePercentage}%"
                        ></div>
                    </div>

                    <div class="goal-progress-footer">
                        <span>
                            ${safePercentage.toFixed(0)}%
                        </span>

                        <span>
                            ${formatMoney(remaining)}
                            remaining
                        </span>
                    </div>

                    ${
                        goal.deadline
                            ? `
                                <div class="goal-deadline">
                                    Deadline:
                                    ${escapeHTML(
                                        formatDate(
                                            goal.deadline
                                        )
                                    )}
                                </div>
                            `
                            : ""
                    }
                </div>
            `;
        })
        .join("");

    $all("[data-delete-goal]").forEach(
        button => {
            button.addEventListener(
                "click",
                async () => {
                    await deleteGoal(
                        button.dataset.deleteGoal
                    );
                }
            );
        }
    );
}


function setupGoalForm() {
    const form = $("goal-form");

    if (!form) {
        return;
    }

    const goalSelect =
        $("goal-name-select");

    const customGoalGroup =
        $("custom-goal-group");

    if (goalSelect) {
        goalSelect.addEventListener(
            "change",
            () => {
                const isCustom =
                    goalSelect.value === "custom";

                if (customGoalGroup) {
                    customGoalGroup.style.display =
                        isCustom
                            ? ""
                            : "none";
                }
            }
        );
    }

    form.addEventListener("submit", async event => {
        event.preventDefault();

        let name =
            goalSelect?.value || "";

        if (name === "custom") {
            name =
                $("goal-name")?.value.trim() || "";
        }

        const target =
            Number($("goal-target")?.value || 0);

        const current =
            Number($("goal-current")?.value || 0);

        const deadline =
            $("goal-deadline")?.value || "";

        if (!name) {
            showToast(
                "Please enter a goal name.",
                "warning"
            );

            return;
        }

        if (!target || target <= 0) {
            showToast(
                "Please enter a valid target amount.",
                "warning"
            );

            return;
        }

        if (current < 0) {
            showToast(
                "Current amount cannot be negative.",
                "warning"
            );

            return;
        }

        try {
            await fetchJSON("/api/goals", {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    name,
                    target,
                    current,
                    deadline
                })
            });

            showToast(
                "Goal created successfully.",
                "success"
            );

            form.reset();

            if (customGoalGroup) {
                customGoalGroup.style.display =
                    "none";
            }

            closeModal("goal-modal");

            await refreshAll();

            showPage("budget");

        } catch (error) {
            console.error(
                "Create goal error:",
                error
            );

            showToast(
                `Could not create goal: ${error.message}`,
                "error"
            );
        }
    });
}


async function deleteGoal(id) {
    if (!id) {
        return;
    }

    const confirmed = window.confirm(
        "Delete this goal?"
    );

    if (!confirmed) {
        return;
    }

    try {
        await fetchJSON(`/api/goals/${id}`, {
            method: "DELETE"
        });

        showToast(
            "Goal deleted.",
            "success"
        );

        await refreshAll();

    } catch (error) {
        console.error(
            "Delete goal error:",
            error
        );

        showToast(
            `Could not delete goal: ${error.message}`,
            "error"
        );
    }
}


/* =========================================================
   SMART COACH
   ========================================================= */

async function loadSmartCoach() {
    try {
        const data =
            await fetchJSON("/api/dashboard");

        state.dashboard = data;

        renderFinancialHealth(
            data.health || {}
        );

        renderCoachInsights(
            data.insights || []
        );

        renderRecurringExpenses(
            data.recurring_expenses || []
        );

    } catch (error) {
        console.error(
            "Smart Coach error:",
            error
        );

        showToast(
            `Unable to load Smart Coach: ${error.message}`,
            "error"
        );
    }
}


function renderFinancialHealth(health) {
    const scoreElement =
        $("financial-health-score");

    const statusElement =
        $("financial-health-status");

    const score =
        Number(
            health.score ??
            health.health_score ??
            0
        );

    const status =
        health.status ||
        getHealthStatus(score);

    if (scoreElement) {
        scoreElement.textContent =
            Math.round(score);
    }

    if (statusElement) {
        statusElement.textContent =
            status;
    }

    if (scoreElement) {
        scoreElement.classList.remove(
            "excellent",
            "good",
            "fair",
            "poor"
        );

        if (score >= 80) {
            scoreElement.classList.add(
                "excellent"
            );
        } else if (score >= 65) {
            scoreElement.classList.add(
                "good"
            );
        } else if (score >= 45) {
            scoreElement.classList.add(
                "fair"
            );
        } else {
            scoreElement.classList.add(
                "poor"
            );
        }
    }
}


function getHealthStatus(score) {
    if (score >= 80) {
        return "Excellent";
    }

    if (score >= 65) {
        return "Good";
    }

    if (score >= 45) {
        return "Fair";
    }

    return "Needs Attention";
}


function renderCoachInsights(insights) {
    const container =
        $("coach-insights");

    if (!container) {
        return;
    }

    const cards =
        container.querySelectorAll(
            ".coach-card"
        );

    if (
        !Array.isArray(insights) ||
        insights.length === 0
    ) {
        cards.forEach((card, index) => {
            const title =
                card.querySelector(
                    ".coach-card-title, h3, h4"
                );

            const body =
                card.querySelector(
                    ".coach-card-text, p"
                );

            if (title) {
                title.textContent =
                    "Smart Coach";
            }

            if (body) {
                body.textContent =
                    "Add more transactions to receive personalized insights.";
            }
        });

        return;
    }

    cards.forEach((card, index) => {
        const insight =
            insights[index];

        if (!insight) {
            return;
        }

        let title = "Financial Insight";
        let text = "";

        if (typeof insight === "string") {
            text = insight;
        } else {
            title =
                insight.title ||
                insight.heading ||
                insight.type ||
                "Financial Insight";

            text =
                insight.message ||
                insight.description ||
                insight.text ||
                "";
        }

        const titleElement =
            card.querySelector(
                ".coach-card-title, h3, h4"
            );

        const bodyElement =
            card.querySelector(
                ".coach-card-text, p"
            );

        if (titleElement) {
            titleElement.textContent =
                title;
        }

        if (bodyElement) {
            bodyElement.textContent =
                text;
        }
    });
}


/* =========================================================
   RECURRING EXPENSES
   ========================================================= */

async function loadRecurringExpenses() {
    try {
        const data =
            await fetchJSON(
                "/api/recurring-expenses"
            );

        state.recurringExpenses =
            data.recurring_expenses ||
            data.expenses ||
            [];

        renderRecurringExpenses(
            state.recurringExpenses
        );

    } catch (error) {
        console.error(
            "Recurring expenses error:",
            error
        );
    }
}


function renderRecurringExpenses(expenses) {
    const container =
        $("recurring-expenses-list");

    if (!container) {
        return;
    }

    if (
        !Array.isArray(expenses) ||
        expenses.length === 0
    ) {
        container.innerHTML = `
            <div class="empty-state">
                <p>
                    No recurring expenses detected.
                </p>
            </div>
        `;

        return;
    }

    container.innerHTML = expenses
        .map(expense => {
            const confidence =
                Number(
                    expense.confidence
                );

            const confidenceText =
                Number.isFinite(confidence)
                    ? `${confidence.toFixed(0)}% confidence`
                    : "Detected pattern";

            return `
                <div class="recurring-expense-card">
                    <div class="recurring-expense-main">
                        <div class="recurring-expense-icon">
                            🔁
                        </div>

                        <div>
                            <h4>
                                ${escapeHTML(
                                    expense.description ||
                                    "Recurring expense"
                                )}
                            </h4>

                            <p>
                                ${escapeHTML(
                                    expense.category ||
                                    "Other"
                                )}
                                ·
                                ${escapeHTML(
                                    expense.frequency ||
                                    "Recurring"
                                )}
                            </p>
                        </div>
                    </div>

                    <div class="recurring-expense-amount">
                        <strong>
                            ${formatMoney(
                                expense.amount
                            )}
                        </strong>

                        ${
                            expense.estimated_monthly
                                ? `
                                    <span>
                                        ≈
                                        ${formatMoney(
                                            expense.estimated_monthly
                                        )}
                                        / month
                                    </span>
                                `
                                : ""
                        }

                        <small>
                            ${escapeHTML(
                                confidenceText
                            )}
                        </small>
                    </div>
                </div>
            `;
        })
        .join("");
}


/* =========================================================
   AI STATUS
   ========================================================= */

async function loadAIStatus() {
    const badge =
        $("ai-status-badge");

    try {
        const data =
            await fetchJSON("/api/ai-status");

        if (!badge) {
            return;
        }

        const configured =
            Boolean(data.configured);

        const model =
            data.model || "";

        if (configured) {
            badge.textContent =
                model
                    ? `AI Active · ${model}`
                    : "AI Active";

            badge.classList.add("active");
            badge.classList.remove("offline");
        } else {
            badge.textContent =
                "Smart Local Mode";

            badge.classList.add("offline");
            badge.classList.remove("active");
        }

    } catch (error) {
        console.error(
            "AI status error:",
            error
        );

        if (badge) {
            badge.textContent =
                "Smart Local Mode";

            badge.classList.add("offline");
            badge.classList.remove("active");
        }
    }
}


/* =========================================================
   AI CHAT
   ========================================================= */

function setupAIChat() {
    const form =
        $("ai-chat-form");

    const input =
        $("ai-chat-input");

    if (!form || !input) {
        return;
    }

    form.addEventListener(
        "submit",
        async event => {
            event.preventDefault();

            const message =
                input.value.trim();

            if (!message) {
                return;
            }

            appendChatMessage(
                message,
                "user"
            );

            input.value = "";

            const loadingMessage =
                appendChatMessage(
                    "Thinking...",
                    "assistant",
                    true
                );

            const submitButton =
                $("ai-chat-submit");

            if (submitButton) {
                submitButton.disabled =
                    true;
            }

            try {
                const data =
                    await fetchJSON(
                        "/api/ai-chat",
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body: JSON.stringify({
                                message
                            })
                        }
                    );

                if (loadingMessage) {
                    loadingMessage.remove();
                }

                appendChatMessage(
                    data.answer ||
                    data.message ||
                    "I couldn't generate a response.",
                    "assistant"
                );

            } catch (error) {
                console.error(
                    "AI chat error:",
                    error
                );

                if (loadingMessage) {
                    loadingMessage.remove();
                }

                appendChatMessage(
                    `Sorry, I couldn't process that request. ${error.message}`,
                    "assistant"
                );

            } finally {
                if (submitButton) {
                    submitButton.disabled =
                        false;
                }

                input.focus();
            }
        }
    );
}


function appendChatMessage(
    message,
    sender = "assistant",
    temporary = false
) {
    const container =
        $("ai-chat-messages");

    if (!container) {
        return null;
    }

    const messageElement =
        document.createElement("div");

    messageElement.className =
        `chat-message ${sender}`;

    if (temporary) {
        messageElement.classList.add(
            "temporary"
        );
    }

    const bubble =
        document.createElement("div");

    bubble.className =
        "chat-bubble";

    bubble.textContent =
        message;

    messageElement.appendChild(
        bubble
    );

    container.appendChild(
        messageElement
    );

    container.scrollTop =
        container.scrollHeight;

    return messageElement;
}


/* =========================================================
   VOICE INPUT
   ========================================================= */

function setupVoiceInput() {
    const button =
        $("voice-input-btn");

    const input =
        $("ai-chat-input");

    const status =
        $("voice-status");

    if (!button || !input) {
        return;
    }

    const SpeechRecognition =
        window.SpeechRecognition ||
        window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        button.addEventListener(
            "click",
            () => {
                showToast(
                    "Voice input is not supported by this browser.",
                    "warning"
                );
            }
        );

        return;
    }

    const recognition =
        new SpeechRecognition();

    recognition.lang = "en-IN";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    let listening = false;

    button.addEventListener(
        "click",
        () => {
            if (listening) {
                recognition.stop();
                return;
            }

            try {
                recognition.start();
            } catch (error) {
                console.error(
                    "Voice recognition start error:",
                    error
                );
            }
        }
    );

    recognition.addEventListener(
        "start",
        () => {
            listening = true;

            button.classList.add(
                "recording"
            );

            if (status) {
                status.textContent =
                    "Listening...";
            }
        }
    );

    recognition.addEventListener(
        "result",
        event => {
            const transcript =
                event.results?.[0]?.[0]?.transcript ||
                "";

            if (transcript) {
                input.value =
                    `${input.value} ${transcript}`
                        .trim();

                input.focus();
            }
        }
    );

    recognition.addEventListener(
        "end",
        () => {
            listening = false;

            button.classList.remove(
                "recording"
            );

            if (status) {
                status.textContent =
                    "";
            }
        }
    );

    recognition.addEventListener(
        "error",
        event => {
            listening = false;

            button.classList.remove(
                "recording"
            );

            if (status) {
                status.textContent =
                    "";
            }

            console.error(
                "Speech recognition error:",
                event.error
            );

            if (
                event.error !==
                "no-speech"
            ) {
                showToast(
                    "Voice input could not be started.",
                    "error"
                );
            }
        }
    );
}


/* =========================================================
   SMART COACH BUTTONS
   ========================================================= */

function setupCoachActions() {
    const addButton =
        $("coach-add-transaction-btn");

    if (addButton) {
        addButton.addEventListener(
            "click",
            () => {
                openModal(
                    "transaction-modal"
                );
            }
        );
    }
}


/* =========================================================
   VIEW INSIGHTS BUTTON
   ========================================================= */

function setupViewInsightsButton() {
    const button =
        $("view-insights-btn");

    if (!button) {
        return;
    }

    button.addEventListener(
        "click",
        () => {
            showPage("coach");
        }
    );
}


/* =========================================================
   CREATE BUTTONS
   ========================================================= */

function setupCreateButtons() {
    const createTransaction =
        $("add-transaction-btn");

    if (createTransaction) {
        createTransaction.addEventListener(
            "click",
            () => {
                openModal(
                    "transaction-modal"
                );
            }
        );
    }

    const createBudget =
        $("create-budget-btn");

    if (createBudget) {
        createBudget.addEventListener(
            "click",
            () => {
                openModal(
                    "budget-modal"
                );
            }
        );
    }

    const emptyBudget =
        $("empty-create-budget-btn");

    if (emptyBudget) {
        emptyBudget.addEventListener(
            "click",
            () => {
                openModal(
                    "budget-modal"
                );
            }
        );
    }

    const createGoal =
        $("create-goal-btn");

    if (createGoal) {
        createGoal.addEventListener(
            "click",
            () => {
                openModal(
                    "goal-modal"
                );
            }
        );
    }

    const emptyGoal =
        $("empty-create-goal-btn");

    if (emptyGoal) {
        emptyGoal.addEventListener(
            "click",
            () => {
                openModal(
                    "goal-modal"
                );
            }
        );
    }
}


/* =========================================================
   MODAL EVENTS
   ========================================================= */

function setupModalEvents() {
    $all("[data-close-modal]").forEach(
        button => {
            button.addEventListener(
                "click",
                () => {
                    const modalId =
                        button.dataset.closeModal;

                    closeModal(modalId);
                }
            );
        }
    );

    $all(".modal").forEach(modal => {
        modal.addEventListener(
            "click",
            event => {
                if (
                    event.target === modal
                ) {
                    closeModal(
                        modal.id
                    );
                }
            }
        );
    });

    document.addEventListener(
        "keydown",
        event => {
            if (
                event.key === "Escape"
            ) {
                closeAllModals();
            }
        }
    );
}


/* =========================================================
   FORM / INPUT HELPERS
   ========================================================= */

function setupAmountInputs() {
    [
        $("transaction-amount"),
        $("budget-amount"),
        $("goal-target"),
        $("goal-current")
    ]
        .filter(Boolean)
        .forEach(input => {
            input.addEventListener(
                "input",
                () => {
                    if (
                        Number(input.value) < 0
                    ) {
                        input.value = 0;
                    }
                }
            );
        });
}


/* =========================================================
   REFRESH EVERYTHING
   ========================================================= */

async function refreshAll() {
    if (state.isLoading) {
        return;
    }

    state.isLoading = true;

    try {
        await Promise.allSettled([
            loadTransactions(),
            loadBudgets(),
            loadGoals(),
            loadDashboard(),
            loadRecurringExpenses(),
            loadAIStatus()
        ]);

    } finally {
        state.isLoading = false;
    }
}


/* =========================================================
   INITIAL APPLICATION SETUP
   ========================================================= */

function initializeDefaults() {
    populateYearSelectors();
    setCurrentMonthSelectors();

    const transactionDate =
        $("transaction-date");

    if (
        transactionDate &&
        !transactionDate.value
    ) {
        transactionDate.value =
            getTodayString();
    }

    const goalCustomGroup =
        $("custom-goal-group");

    if (goalCustomGroup) {
        goalCustomGroup.style.display =
            "none";
    }
}


/* =========================================================
   INITIALIZE APPLICATION
   ========================================================= */

async function initializeApp() {
    console.log(
        "FinFlow initializing..."
    );

    initializeDefaults();

    setupNavigation();
    setupChartFilters();

    setupTransactionFilters();
    setupTransactionForm();
    setupCategorySuggestion();

    setupStatementUpload();

    setupBudgetForm();

    setupGoalForm();

    setupAIChat();
    setupVoiceInput();

    setupCoachActions();
    setupViewInsightsButton();

    setupCreateButtons();
    setupModalEvents();

    setupAmountInputs();

    await refreshAll();

    showPage("home");

    console.log(
        "FinFlow initialized successfully."
    );
}


/* =========================================================
   START APPLICATION
   ========================================================= */

if (
    document.readyState === "loading"
) {
    document.addEventListener(
        "DOMContentLoaded",
        initializeApp
    );
} else {
    initializeApp();
}