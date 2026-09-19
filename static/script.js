/* =========================================================
   FINFLOW
   Money in Motion
   Main Frontend JavaScript
========================================================= */


/* =========================================================
   GLOBAL VARIABLES
========================================================= */

let transactions = [];

let incomeExpenseChart = null;
let spendingChart = null;

let currentFilter = "all";

const today = new Date();

let selectedYear = today.getFullYear();
let selectedMonth = today.getMonth() + 1;


/* =========================================================
   HELPER FUNCTIONS
========================================================= */

function formatMoney(value) {

    value = Number(value || 0);

    return "₹" + value.toLocaleString("en-IN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}


function formatShortMoney(value) {

    value = Number(value || 0);

    return "₹" + value.toLocaleString("en-IN", {
        maximumFractionDigits: 0
    });
}


function escapeHTML(value) {

    if (value === null || value === undefined) {
        return "";
    }

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function getTodayString() {

    const year = today.getFullYear();

    const month = String(
        today.getMonth() + 1
    ).padStart(2, "0");

    const day = String(
        today.getDate()
    ).padStart(2, "0");

    return `${year}-${month}-${day}`;
}


async function fetchJSON(url, options = {}) {

    const response = await fetch(
        url,
        options
    );

    if (!response.ok) {

        let message = "Something went wrong.";

        try {

            const data = await response.json();

            message =
                data.message ||
                message;

        } catch (error) {
            // Ignore JSON parsing error
        }

        throw new Error(message);
    }

    return response.json();
}


/* =========================================================
   PAGE NAVIGATION
========================================================= */

const navItems =
    document.querySelectorAll(".nav-item");

const pages =
    document.querySelectorAll(".page-view");


function showPage(viewName) {

    navItems.forEach(item => {

        item.classList.toggle(
            "active",
            item.dataset.view === viewName
        );

    });


    pages.forEach(page => {

        page.classList.toggle(
            "active-view",
            page.id === `${viewName}-view`
        );

    });


    if (viewName === "home") {

        loadDashboard();

    }

    if (viewName === "transactions") {

        loadTransactions();

    }

    if (viewName === "budget") {

        loadBudgets();
        loadGoals();

    }

    if (viewName === "coach") {

        loadSmartCoach();

    }
}


navItems.forEach(item => {

    item.addEventListener(
        "click",
        () => {

            showPage(
                item.dataset.view
            );

        }
    );

});


/* =========================================================
   VIEW INSIGHTS BUTTON
========================================================= */

const viewInsightsButton =
    document.getElementById(
        "view-insights-btn"
    );


if (viewInsightsButton) {

    viewInsightsButton.addEventListener(
        "click",
        () => {

            showPage("coach");

        }
    );

}


/* =========================================================
   MODAL FUNCTIONS
========================================================= */

function openModal(modalId) {

    const modal =
        document.getElementById(modalId);

    if (!modal) {
        return;
    }

    modal.hidden = false;

    modal.style.display = "flex";

}


function closeModal(modalId) {

    const modal =
        document.getElementById(modalId);

    if (!modal) {
        return;
    }

    modal.hidden = true;

    modal.style.display = "none";

}


/* =========================================================
   CLOSE BUTTONS
========================================================= */

document
    .querySelectorAll("[data-close-modal]")
    .forEach(button => {

        button.addEventListener(
            "click",
            () => {

                closeModal(
                    button.dataset.closeModal
                );

            }
        );

    });


/* Close when clicking outside modal */

document
    .querySelectorAll(".modal-overlay")
    .forEach(modal => {

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


/* =========================================================
   SUMMARY CARDS
========================================================= */

async function loadDashboard() {

    try {

        const data =
            await fetchJSON(
                "/api/dashboard"
            );


        const summary =
            data.summary;


        const balanceValue =
            document.getElementById(
                "balance-value"
            );

        const incomeValue =
            document.getElementById(
                "income-value"
            );

        const expenseValue =
            document.getElementById(
                "expense-value"
            );

        const savingsValue =
            document.getElementById(
                "savings-value"
            );


        if (balanceValue) {

            balanceValue.textContent =
                formatMoney(
                    summary.balance
                );

        }


        if (incomeValue) {

            incomeValue.textContent =
                formatMoney(
                    summary.income
                );

        }


        if (expenseValue) {

            expenseValue.textContent =
                formatMoney(
                    summary.expenses
                );

        }


        if (savingsValue) {

            savingsValue.textContent =
                `${Number(
                    summary.savings_rate || 0
                ).toFixed(1)}%`;

        }


        updateChange(
            "balance-change",
            summary.changes?.balance
        );

        updateChange(
            "income-change",
            summary.changes?.income
        );

        updateChange(
            "expense-change",
            summary.changes?.expenses
        );

        updateChange(
            "savings-change",
            summary.changes?.savings_rate
        );


        renderHomeInsights(
            data.insights || []
        );


        loadHomeBudgetPreview();

    } catch (error) {

        console.error(
            "Dashboard error:",
            error
        );

    }


    await loadCharts();

}


function updateChange(
    elementId,
    value
) {

    const element =
        document.getElementById(
            elementId
        );

    if (!element) {
        return;
    }


    if (
        value === null ||
        value === undefined ||
        Number.isNaN(Number(value))
    ) {

        element.textContent =
            "— from last month";

        element.className =
            "stat-change";

        return;
    }


    const number =
        Number(value);


    const rounded =
        Math.abs(number).toFixed(1);


    let arrow = "";

    if (number > 0) {

        arrow = "↑";

    } else if (number < 0) {

        arrow = "↓";

    } else {

        arrow = "→";

    }


    element.textContent =
        `${arrow} ${rounded}% from last month`;


    element.className =
        "stat-change " +
        (
            number > 0
                ? "positive"
                : number < 0
                    ? "negative"
                    : ""
        );

}


/* =========================================================
   YEAR SELECTORS
========================================================= */

function populateYearSelectors() {

    const selectors = [

        document.getElementById(
            "cashflow-year"
        ),

        document.getElementById(
            "spending-year"
        )

    ];


    const currentYear =
        new Date().getFullYear();


    selectors.forEach(select => {

        if (!select) {
            return;
        }


        select.innerHTML = "";


        for (
            let year = currentYear;
            year >= currentYear - 5;
            year--
        ) {

            const option =
                document.createElement(
                    "option"
                );

            option.value =
                year;

            option.textContent =
                year;


            if (
                year === selectedYear
            ) {

                option.selected = true;

            }


            select.appendChild(
                option
            );

        }

    });

}


/* =========================================================
   MONTH SELECTORS
========================================================= */

function setInitialMonthSelectors() {

    const cashflowMonth =
        document.getElementById(
            "cashflow-month"
        );

    const spendingMonth =
        document.getElementById(
            "spending-month"
        );


    if (cashflowMonth) {

        cashflowMonth.value =
            String(selectedMonth);

    }


    if (spendingMonth) {

        spendingMonth.value =
            String(selectedMonth);

    }

}


/* =========================================================
   CHART CONTROLS
========================================================= */

const cashflowYear =
    document.getElementById(
        "cashflow-year"
    );

const cashflowMonth =
    document.getElementById(
        "cashflow-month"
    );

const spendingYear =
    document.getElementById(
        "spending-year"
    );

const spendingMonth =
    document.getElementById(
        "spending-month"
    );


if (cashflowYear) {

    cashflowYear.addEventListener(
        "change",
        async () => {

            selectedYear =
                Number(
                    cashflowYear.value
                );


            if (spendingYear) {

                spendingYear.value =
                    String(selectedYear);

            }


            await loadCharts();

            await loadSelectedMonthComparison();

        }
    );

}


if (cashflowMonth) {

    cashflowMonth.addEventListener(
        "change",
        async () => {

            selectedMonth =
                Number(
                    cashflowMonth.value
                );


            if (spendingMonth) {

                spendingMonth.value =
                    String(selectedMonth);

            }


            await loadSpendingChart();

            await loadSelectedMonthComparison();

        }
    );

}


if (spendingYear) {

    spendingYear.addEventListener(
        "change",
        async () => {

            selectedYear =
                Number(
                    spendingYear.value
                );


            if (cashflowYear) {

                cashflowYear.value =
                    String(selectedYear);

            }


            await loadCharts();

            await loadSelectedMonthComparison();

        }
    );

}


if (spendingMonth) {

    spendingMonth.addEventListener(
        "change",
        async () => {

            selectedMonth =
                Number(
                    spendingMonth.value
                );


            if (cashflowMonth) {

                cashflowMonth.value =
                    String(selectedMonth);

            }


            await loadSpendingChart();

            await loadSelectedMonthComparison();

        }
    );

}


/* =========================================================
   CHARTS
========================================================= */

async function loadCharts() {

    await loadIncomeExpenseChart();

    await loadSpendingChart();

}


/* =========================================================
   INCOME VS EXPENSES BAR CHART
========================================================= */

async function loadIncomeExpenseChart() {

    try {

        const data =
            await fetchJSON(
                `/api/monthly-summary?year=${selectedYear}`
            );


        const canvas =
            document.getElementById(
                "income-expense-chart"
            );


        if (!canvas) {
            return;
        }


        const labels =
            data.map(
                item =>
                    item.month_name.substring(
                        0,
                        3
                    )
            );


        const income =
            data.map(
                item =>
                    Number(
                        item.income || 0
                    )
            );


        const expenses =
            data.map(
                item =>
                    Number(
                        item.expenses || 0
                    )
            );


        if (incomeExpenseChart) {

            incomeExpenseChart.destroy();

        }


        incomeExpenseChart =
            new Chart(
                canvas,
                {

                    type: "bar",

                    data: {

                        labels: labels,

                        datasets: [

                            {
                                label: "Income",

                                data: income,

                                backgroundColor:
                                    "rgba(15, 174, 143, 0.75)",

                                borderRadius: 6
                            },

                            {
                                label: "Expenses",

                                data: expenses,

                                backgroundColor:
                                    "rgba(230, 104, 104, 0.70)",

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

                                position: "bottom"

                            },

                            tooltip: {

                                callbacks: {

                                    label: function (
                                        context
                                    ) {

                                        return (
                                            context.dataset.label +
                                            ": " +
                                            formatMoney(
                                                context.raw
                                            )
                                        );

                                    }

                                }

                            }

                        },

                        scales: {

                            y: {

                                beginAtZero: true,

                                ticks: {

                                    callback: function (
                                        value
                                    ) {

                                        return formatShortMoney(
                                            value
                                        );

                                    }

                                }

                            }

                        }

                    }

                }
            );

    } catch (error) {

        console.error(
            "Income/expense chart error:",
            error
        );

    }

}


/* =========================================================
   SPENDING PIE / DOUGHNUT CHART
========================================================= */

async function loadSpendingChart() {

    try {

        const data =
            await fetchJSON(
                `/api/spending-by-category?year=${selectedYear}&month=${selectedMonth}`
            );


        const canvas =
            document.getElementById(
                "spending-chart"
            );


        if (!canvas) {
            return;
        }


        const labels =
            data.map(
                item =>
                    item.category
            );


        const values =
            data.map(
                item =>
                    Number(
                        item.total || 0
                    )
            );


        const total =
            values.reduce(
                (sum, value) =>
                    sum + value,
                0
            );


        const totalElement =
            document.getElementById(
                "spending-total"
            );


        if (totalElement) {

            totalElement.textContent =
                formatShortMoney(
                    total
                );

        }


        if (spendingChart) {

            spendingChart.destroy();

        }


        if (values.length === 0) {

            spendingChart =
                new Chart(
                    canvas,
                    {

                        type: "doughnut",

                        data: {

                            labels: [
                                "No spending"
                            ],

                            datasets: [

                                {

                                    data: [1],

                                    backgroundColor: [
                                        "#dcebe8"
                                    ],

                                    borderWidth: 0

                                }

                            ]

                        },

                        options: {

                            responsive: true,

                            maintainAspectRatio: false,

                            cutout: "65%",

                            plugins: {

                                legend: {

                                    display: false

                                }

                            }

                        }

                    }
                );

            return;
        }


        const chartColors = [

            "#0fae8f",
            "#087f70",
            "#55cbb6",
            "#9be3d4",
            "#36a890",
            "#70d5c2",
            "#176f63",
            "#b7eadf",
            "#4bb39f"

        ];


        spendingChart =
            new Chart(
                canvas,
                {

                    type: "doughnut",

                    data: {

                        labels: labels,

                        datasets: [

                            {

                                data: values,

                                backgroundColor:
                                    chartColors.slice(
                                        0,
                                        values.length
                                    ),

                                borderWidth: 2,

                                borderColor:
                                    "#ffffff"

                            }

                        ]

                    },

                    options: {

                        responsive: true,

                        maintainAspectRatio: false,

                        cutout: "62%",

                        plugins: {

                            legend: {

                                position: "right"

                            },

                            tooltip: {

                                callbacks: {

                                    label: function (
                                        context
                                    ) {

                                        return (
                                            context.label +
                                            ": " +
                                            formatMoney(
                                                context.raw
                                            )
                                        );

                                    }

                                }

                            }

                        }

                    }

                }
            );

    } catch (error) {

        console.error(
            "Spending chart error:",
            error
        );

    }

}


/* =========================================================
   SELECTED MONTH COMPARISON
========================================================= */

async function loadSelectedMonthComparison() {

    try {

        const data =
            await fetchJSON(
                `/api/monthly-comparison?year=${selectedYear}&month=${selectedMonth}`
            );


        /*
         The main cards remain lifetime totals.
         The selected month controls the comparison
         information used by the dashboard.
        */

        console.log(
            "Selected month comparison:",
            data
        );

    } catch (error) {

        console.error(
            "Monthly comparison error:",
            error
        );

    }

}


/* =========================================================
   TRANSACTIONS
========================================================= */

async function loadTransactions() {

    try {

        transactions =
            await fetchJSON(
                "/api/transactions"
            );


        displayTransactions(
            transactions
        );

    } catch (error) {

        console.error(
            "Transactions error:",
            error
        );

    }

}


function displayTransactions(data) {

    const table =
        document.getElementById(
            "transaction-table-body"
        );


    if (!table) {
        return;
    }


    if (!data.length) {

        table.innerHTML = `

            <tr>

                <td colspan="5">
                    No transactions yet
                </td>

            </tr>

        `;

        return;
    }


    table.innerHTML =
        data.map(
            transaction => {

                const amount =
                    Number(
                        transaction.amount || 0
                    );


                const sign =
                    transaction.type === "income"
                        ? "+"
                        : "-";


                return `

                    <tr>

                        <td>
                            ${escapeHTML(
                                transaction.date
                            )}
                        </td>

                        <td>
                            ${escapeHTML(
                                transaction.description ||
                                "—"
                            )}
                        </td>

                        <td>
                            ${escapeHTML(
                                transaction.category
                            )}
                        </td>

                        <td>
                            ${escapeHTML(
                                transaction.type
                            )}
                        </td>

                        <td>
                            ${sign}${formatMoney(
                                amount
                            )}
                        </td>

                    </tr>

                `;

            }
        ).join("");

}


/* =========================================================
   TRANSACTION SEARCH
========================================================= */

const searchBox =
    document.getElementById(
        "transaction-search"
    );


if (searchBox) {

    searchBox.addEventListener(
        "input",
        () => {

            const text =
                searchBox.value
                    .toLowerCase()
                    .trim();


            let filtered =
                transactions;


            if (currentFilter !== "all") {

                filtered =
                    filtered.filter(
                        transaction =>
                            transaction.type ===
                            currentFilter
                    );

            }


            if (text) {

                filtered =
                    filtered.filter(
                        transaction => {

                            const description =
                                (
                                    transaction.description ||
                                    ""
                                ).toLowerCase();

                            const category =
                                (
                                    transaction.category ||
                                    ""
                                ).toLowerCase();

                            const type =
                                (
                                    transaction.type ||
                                    ""
                                ).toLowerCase();

                            return (
                                description.includes(text) ||
                                category.includes(text) ||
                                type.includes(text)
                            );

                        }
                    );

            }


            displayTransactions(
                filtered
            );

        }
    );

}


/* =========================================================
   TRANSACTION FILTERS
========================================================= */

document
    .querySelectorAll(".filter-tab")
    .forEach(button => {

        button.addEventListener(
            "click",
            () => {

                document
                    .querySelectorAll(
                        ".filter-tab"
                    )
                    .forEach(
                        item =>
                            item.classList.remove(
                                "active"
                            )
                    );


                button.classList.add(
                    "active"
                );


                currentFilter =
                    button.dataset.filter ||
                    "all";


                applyTransactionFilters();

            }
        );

    });


function applyTransactionFilters() {

    const text =
        searchBox
            ? searchBox.value
                .toLowerCase()
                .trim()
            : "";


    let filtered =
        [...transactions];


    if (
        currentFilter !==
        "all"
    ) {

        filtered =
            filtered.filter(
                transaction =>
                    transaction.type ===
                    currentFilter
            );

    }


    if (text) {

        filtered =
            filtered.filter(
                transaction => {

                    const description =
                        (
                            transaction.description ||
                            ""
                        ).toLowerCase();

                    const category =
                        (
                            transaction.category ||
                            ""
                        ).toLowerCase();

                    return (
                        description.includes(text) ||
                        category.includes(text)
                    );

                }
            );

    }


    displayTransactions(
        filtered
    );

}


/* =========================================================
   OPEN ADD TRANSACTION MODAL
========================================================= */

function openTransactionModal() {

    const form =
        document.getElementById(
            "transaction-form"
        );


    if (form) {

        form.reset();

    }


    const dateInput =
        document.getElementById(
            "transaction-date"
        );


    if (dateInput) {

        dateInput.value =
            getTodayString();

    }


    openModal(
        "transaction-modal"
    );

}


/* =========================================================
   ADD TRANSACTION BUTTONS
========================================================= */

const addTransactionButton =
    document.getElementById(
        "add-transaction-btn"
    );


const coachAddTransactionButton =
    document.getElementById(
        "coach-add-transaction-btn"
    );


if (addTransactionButton) {

    addTransactionButton.addEventListener(
        "click",
        openTransactionModal
    );

}


if (coachAddTransactionButton) {

    coachAddTransactionButton.addEventListener(
        "click",
        openTransactionModal
    );

}


/* =========================================================
   ADD TRANSACTION FORM
========================================================= */

const transactionForm =
    document.getElementById(
        "transaction-form"
    );


if (transactionForm) {

    transactionForm.addEventListener(
        "submit",
        async event => {

            event.preventDefault();


            const type =
                document.getElementById(
                    "transaction-type"
                ).value;


            const amount =
                document.getElementById(
                    "transaction-amount"
                ).value;


            const category =
                document.getElementById(
                    "transaction-category"
                ).value;


            const description =
                document.getElementById(
                    "transaction-description"
                ).value;


            const date =
                document.getElementById(
                    "transaction-date"
                ).value;


            if (
                !type ||
                !amount ||
                !category ||
                !date
            ) {

                alert(
                    "Please fill all required fields."
                );

                return;

            }


            try {

                const result =
                    await fetchJSON(
                        "/api/transactions",
                        {

                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body:
                                JSON.stringify({

                                    type:
                                        type,

                                    amount:
                                        Number(
                                            amount
                                        ),

                                    category:
                                        category,

                                    description:
                                        description,

                                    date:
                                        date

                                })

                        }
                    );


                alert(
                    result.message ||
                    "Transaction added successfully."
                );


                closeModal(
                    "transaction-modal"
                );


                await refreshAll();


                showPage(
                    "transactions"
                );

            } catch (error) {

                alert(
                    error.message
                );

            }

        }
    );

}


/* =========================================================
   CSV UPLOAD
========================================================= */

const uploadButton =
    document.getElementById(
        "upload-statement-btn"
    );


const statementFile =
    document.getElementById(
        "statement-file"
    );


if (uploadButton && statementFile) {

    uploadButton.addEventListener(
        "click",
        () => {

            statementFile.click();

        }
    );


    statementFile.addEventListener(
        "change",
        async () => {

            if (
                !statementFile.files ||
                !statementFile.files.length
            ) {

                return;

            }


            const file =
                statementFile.files[0];


            const formData =
                new FormData();


            formData.append(
                "file",
                file
            );


            try {

                const result =
                    await fetchJSON(
                        "/api/upload-statement",
                        {

                            method: "POST",

                            body:
                                formData

                        }
                    );


                alert(
                    result.message ||
                    `${result.imported} transactions imported`
                );


                statementFile.value =
                    "";


                await refreshAll();


                showPage(
                    "transactions"
                );

            } catch (error) {

                alert(
                    error.message
                );

            }

        }
    );

}


/* =========================================================
   BUDGETS
========================================================= */

async function loadBudgets() {

    try {

        const data =
            await fetchJSON(
                `/api/budget-progress?year=${selectedYear}&month=${selectedMonth}`
            );


        renderBudgets(
            data
        );


    } catch (error) {

        console.error(
            "Budget error:",
            error
        );

    }

}


function renderBudgets(
    budgets
) {

    const container =
        document.getElementById(
            "budget-list"
        );


    if (!container) {
        return;
    }


    if (!budgets.length) {

        container.innerHTML = `

            <div class="empty-state">

                <p>
                    No budgets created yet.
                </p>

                <button
                    class="primary-button"
                    type="button"
                    id="dynamic-create-budget-btn"
                >
                    + Create Budget
                </button>

            </div>

        `;


        const button =
            document.getElementById(
                "dynamic-create-budget-btn"
            );


        if (button) {

            button.addEventListener(
                "click",
                openBudgetModal
            );

        }


        return;
    }


    container.innerHTML =
        budgets.map(
            budget => {

                const percentage =
                    Math.min(
                        Number(
                            budget.percentage || 0
                        ),
                        100
                    );


                const actualPercentage =
                    Number(
                        budget.percentage || 0
                    );


                return `

                    <div class="budget-item">

                        <div
                            class="budget-item-header"
                        >

                            <div>

                                <span>
                                    ${categoryIcon(
                                        budget.category
                                    )}
                                    ${escapeHTML(
                                        budget.category
                                    )}
                                </span>

                                <p>
                                    ${formatMoney(
                                        budget.spent
                                    )}
                                    /
                                    ${formatMoney(
                                        budget.budget
                                    )}
                                </p>

                            </div>

                            <strong>
                                ${actualPercentage.toFixed(0)}%
                            </strong>

                        </div>


                        <div class="progress-bar large">

                            <div
                                class="progress-fill"
                                style="width: ${percentage}%"
                            >
                            </div>

                        </div>

                    </div>

                `;

            }
        ).join("");

}


/* =========================================================
   HOME BUDGET PREVIEW
========================================================= */

async function loadHomeBudgetPreview() {

    const container =
        document.getElementById(
            "home-budget-progress"
        );


    if (!container) {
        return;
    }


    try {

        const budgets =
            await fetchJSON(
                `/api/budget-progress?year=${selectedYear}&month=${selectedMonth}`
            );


        if (!budgets.length) {

            container.innerHTML = `

                <div class="empty-state">

                    <p>
                        No budgets created yet.
                    </p>

                </div>

            `;

            return;
        }


        container.innerHTML =
            budgets.slice(0, 3).map(
                budget => {

                    const percentage =
                        Math.min(
                            Number(
                                budget.percentage || 0
                            ),
                            100
                        );


                    return `

                        <div class="budget-preview-item">

                            <div>

                                <strong>
                                    ${categoryIcon(
                                        budget.category
                                    )}
                                    ${escapeHTML(
                                        budget.category
                                    )}
                                </strong>

                                <span>
                                    ${formatMoney(
                                        budget.spent
                                    )}
                                    /
                                    ${formatMoney(
                                        budget.budget
                                    )}
                                </span>

                            </div>


                            <div class="progress-bar">

                                <div
                                    class="progress-fill"
                                    style="width:${percentage}%"
                                ></div>

                            </div>

                        </div>

                    `;

                }
            ).join("");

    } catch (error) {

        console.error(
            "Home budget preview error:",
            error
        );

    }

}


/* =========================================================
   CATEGORY ICON
========================================================= */

function categoryIcon(
    category
) {

    const icons = {

        Food: "🍔",

        Transport: "🚗",

        Shopping: "🛍️",

        Education: "📚",

        Bills: "📄",

        Entertainment: "🎬",

        Health: "❤️",

        Salary: "💰",

        Other: "📦"

    };


    return icons[category] ||
        "📦";

}


/* =========================================================
   CREATE BUDGET MODAL
========================================================= */

const createBudgetButton =
    document.getElementById(
        "create-budget-btn"
    );


const emptyCreateBudgetButton =
    document.getElementById(
        "empty-create-budget-btn"
    );


if (createBudgetButton) {

    createBudgetButton.addEventListener(
        "click",
        openBudgetModal
    );

}


if (emptyCreateBudgetButton) {

    emptyCreateBudgetButton.addEventListener(
        "click",
        openBudgetModal
    );

}


function openBudgetModal() {

    const form =
        document.getElementById(
            "budget-form"
        );


    if (form) {

        form.reset();

    }


    openModal(
        "budget-modal"
    );

}


/* =========================================================
   BUDGET FORM
========================================================= */

const budgetForm =
    document.getElementById(
        "budget-form"
    );


if (budgetForm) {

    budgetForm.addEventListener(
        "submit",
        async event => {

            event.preventDefault();


            const category =
                document.getElementById(
                    "budget-category"
                ).value;


            const amount =
                document.getElementById(
                    "budget-amount"
                ).value;


            if (
                !category ||
                !amount
            ) {

                alert(
                    "Please select a category and enter a budget amount."
                );

                return;

            }


            try {

                const result =
                    await fetchJSON(
                        "/api/budgets",
                        {

                            method: "POST",

                            headers: {

                                "Content-Type":
                                    "application/json"

                            },

                            body:
                                JSON.stringify({

                                    category:
                                        category,

                                    amount:
                                        Number(
                                            amount
                                        )

                                })

                        }
                    );


                alert(
                    result.message ||
                    "Budget saved successfully."
                );


                closeModal(
                    "budget-modal"
                );


                await refreshAll();


                showPage(
                    "budget"
                );

            } catch (error) {

                alert(
                    error.message
                );

            }

        }
    );

}


/* =========================================================
   GOALS
========================================================= */

async function loadGoals() {

    try {

        const goals =
            await fetchJSON(
                "/api/goal-progress"
            );


        renderGoals(
            goals
        );


    } catch (error) {

        console.error(
            "Goals error:",
            error
        );

    }

}


function renderGoals(
    goals
) {

    const container =
        document.getElementById(
            "goals-list"
        );


    if (!container) {
        return;
    }


    if (!goals.length) {

        container.innerHTML = `

            <article class="dashboard-card goal-card">

                <div class="goal-card-icon">
                    🎯
                </div>

                <h3>
                    Create your first goal
                </h3>

                <p>
                    Set a target and track your progress.
                </p>

                <button
                    class="primary-button"
                    type="button"
                    id="dynamic-create-goal-btn"
                >
                    + Create Goal
                </button>

            </article>

        `;


        const button =
            document.getElementById(
                "dynamic-create-goal-btn"
            );


        if (button) {

            button.addEventListener(
                "click",
                openGoalModal
            );

        }


        return;
    }


    container.innerHTML =
        goals.map(
            goal => {

                const percentage =
                    Math.min(
                        Number(
                            goal.percentage || 0
                        ),
                        100
                    );


                return `

                    <article
                        class="dashboard-card goal-card"
                    >

                        <div class="goal-card-icon">
                            🎯
                        </div>


                        <p class="card-label">
                            SAVINGS GOAL
                        </p>


                        <h3>
                            ${escapeHTML(
                                goal.name
                            )}
                        </h3>


                        <div class="goal-amount">

                            <strong>
                                ${formatMoney(
                                    goal.current
                                )}
                            </strong>

                            <span>
                                /
                                ${formatMoney(
                                    goal.target
                                )}
                            </span>

                        </div>


                        <div class="progress-bar large">

                            <div
                                class="progress-fill"
                                style="width:${percentage}%"
                            ></div>

                        </div>


                        <p>
                            ${formatMoney(
                                goal.remaining
                            )}
                            remaining
                        </p>


                        <div class="goal-progress-text">

                            ${percentage.toFixed(0)}%
                            complete

                        </div>


                        ${
                            goal.deadline
                                ? `
                                    <p>
                                        Deadline:
                                        ${escapeHTML(
                                            goal.deadline
                                        )}
                                    </p>
                                `
                                : ""
                        }


                        <div class="goal-actions">

                            <button
                                class="secondary-button goal-delete-btn"
                                type="button"
                                data-goal-id="${goal.id}"
                            >
                                Delete
                            </button>

                        </div>

                    </article>

                `;

            }
        ).join("");


    container
        .querySelectorAll(
            ".goal-delete-btn"
        )
        .forEach(button => {

            button.addEventListener(
                "click",
                async () => {

                    await deleteGoal(
                        button.dataset.goalId
                    );

                }
            );

        });

}


/* =========================================================
   CREATE GOAL BUTTONS
========================================================= */

const createGoalButton =
    document.getElementById(
        "create-goal-btn"
    );


const emptyCreateGoalButton =
    document.getElementById(
        "empty-create-goal-btn"
    );


if (createGoalButton) {

    createGoalButton.addEventListener(
        "click",
        openGoalModal
    );

}


if (emptyCreateGoalButton) {

    emptyCreateGoalButton.addEventListener(
        "click",
        openGoalModal
    );

}


/* =========================================================
   OPEN GOAL MODAL
========================================================= */

function openGoalModal() {

    const form =
        document.getElementById(
            "goal-form"
        );


    if (form) {

        form.reset();

    }


    const customGroup =
        document.getElementById(
            "custom-goal-group"
        );


    if (customGroup) {

        customGroup.hidden = true;

    }


    openModal(
        "goal-modal"
    );

}


/* =========================================================
   GOAL PRESET
========================================================= */

const goalPreset =
    document.getElementById(
        "goal-name-select"
    );


if (goalPreset) {

    goalPreset.addEventListener(
        "change",
        () => {

            const customGroup =
                document.getElementById(
                    "custom-goal-group"
                );


            if (!customGroup) {
                return;
            }


            customGroup.hidden =
                goalPreset.value !== "custom";

        }
    );

}


/* =========================================================
   GOAL FORM
========================================================= */

const goalForm =
    document.getElementById(
        "goal-form"
    );


if (goalForm) {

    goalForm.addEventListener(
        "submit",
        async event => {

            event.preventDefault();


            const preset =
                document.getElementById(
                    "goal-name-select"
                ).value;


            const customName =
                document.getElementById(
                    "goal-name"
                ).value.trim();


            const target =
                document.getElementById(
                    "goal-target"
                ).value;


            const current =
                document.getElementById(
                    "goal-current"
                ).value || 0;


            const deadline =
                document.getElementById(
                    "goal-deadline"
                ).value;


            let name = "";


            if (preset === "custom") {

                name =
                    customName;

            } else {

                name =
                    preset;

            }


            if (!name) {

                alert(
                    "Please choose or enter a goal name."
                );

                return;

            }


            if (!target) {

                alert(
                    "Please enter a target amount."
                );

                return;

            }


            try {

                const result =
                    await fetchJSON(
                        "/api/goals",
                        {

                            method: "POST",

                            headers: {

                                "Content-Type":
                                    "application/json"

                            },

                            body:
                                JSON.stringify({

                                    name:
                                        name,

                                    target:
                                        Number(
                                            target
                                        ),

                                    current:
                                        Number(
                                            current
                                        ),

                                    deadline:
                                        deadline ||
                                        null

                                })

                        }
                    );


                alert(
                    result.message ||
                    "Goal created successfully."
                );


                closeModal(
                    "goal-modal"
                );


                await refreshAll();


                showPage(
                    "budget"
                );

            } catch (error) {

                alert(
                    error.message
                );

            }

        }
    );

}


/* =========================================================
   DELETE GOAL
========================================================= */

async function deleteGoal(
    goalId
) {

    const confirmed =
        confirm(
            "Delete this savings goal?"
        );


    if (!confirmed) {
        return;
    }


    try {

        const result =
            await fetchJSON(
                `/api/goals/${goalId}`,
                {

                    method: "DELETE"

                }
            );


        alert(
            result.message ||
            "Goal deleted."
        );


        await refreshAll();


        showPage(
            "budget"
        );

    } catch (error) {

        alert(
            error.message
        );

    }

}


/* =========================================================
   SMART COACH
========================================================= */

async function loadSmartCoach() {

    try {

        const data =
            await fetchJSON(
                "/api/dashboard"
            );


        const health =
            data.health ||
            {};


        const score =
            document.getElementById(
                "financial-health-score"
            );


        const status =
            document.getElementById(
                "financial-health-status"
            );


        if (score) {

            score.textContent =
                health.score ?? 0;

        }


        if (status) {

            status.textContent =
                health.status ||
                "Start adding transactions to receive your financial health score.";

        }


        renderCoachInsights(
            data.insights || []
        );


    } catch (error) {

        console.error(
            "Smart Coach error:",
            error
        );

    }

}


/* =========================================================
   SMART COACH INSIGHTS
========================================================= */

function renderCoachInsights(
    insights
) {

    const cards =
        document.querySelectorAll(
            "#coach-insights .coach-card"
        );


    if (!cards.length) {
        return;
    }


    insights.forEach(
        (insight, index) => {

            if (!cards[index]) {
                return;
            }


            const card =
                cards[index];


            const title =
                card.querySelector(
                    "h3"
                );


            const message =
                card.querySelector(
                    "p:last-child"
                );


            if (title) {

                title.textContent =
                    insight.title ||
                    "Financial Insight";

            }


            if (message) {

                message.textContent =
                    insight.message ||
                    "";

            }

        }
    );

}


/* =========================================================
   HOME INSIGHTS
========================================================= */

function renderHomeInsights(
    insights
) {

    const container =
        document.getElementById(
            "home-insights"
        );


    if (!container) {
        return;
    }


    if (!insights.length) {

        container.innerHTML = `

            <div class="insight-item">

                <span>
                    💡
                </span>

                <div>

                    <strong>
                        Smart Coach
                    </strong>

                    <p>
                        Add more financial activity to receive insights.
                    </p>

                </div>

            </div>

        `;

        return;
    }


    container.innerHTML =
        insights
            .slice(0, 3)
            .map(
                insight => `

                    <div class="insight-item">

                        <span>
                            💡
                        </span>

                        <div>

                            <strong>
                                ${escapeHTML(
                                    insight.title
                                )}
                            </strong>

                            <p>
                                ${escapeHTML(
                                    insight.message
                                )}
                            </p>

                        </div>

                    </div>

                `
            )
            .join("");

}


/* =========================================================
   REFRESH EVERYTHING
========================================================= */

async function refreshAll() {

    await loadTransactions();

    await loadDashboard();

    await loadBudgets();

    await loadGoals();

    await loadSmartCoach();

    await loadCharts();

}


/* =========================================================
   INITIALIZATION
========================================================= */

async function initializeApp() {

    populateYearSelectors();

    setInitialMonthSelectors();


    const transactionDate =
        document.getElementById(
            "transaction-date"
        );


    if (transactionDate) {

        transactionDate.value =
            getTodayString();

    }


    await refreshAll();

}


initializeApp();