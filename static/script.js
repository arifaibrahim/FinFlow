function escapeHTML(value) {

    const div = document.createElement("div");

    div.textContent = String(value ?? "");

    return div.innerHTML;
}


function formatMoney(amount) {

    const value = Number(amount || 0);

    return new Intl.NumberFormat(
        "en-IN",
        {
            style: "currency",
            currency: "INR",
            maximumFractionDigits: 2
        }
    ).format(value);
}


function formatNumber(amount) {

    return Number(amount || 0).toLocaleString(
        "en-IN",
        {
            maximumFractionDigits: 2
        }
    );
}


function getTodayString() {

    const date = new Date();

    const year = date.getFullYear();

    const month = String(
        date.getMonth() + 1
    ).padStart(2, "0");

    const day = String(
        date.getDate()
    ).padStart(2, "0");

    return `${year}-${month}-${day}`;
}


function showToast(message, type = "info") {

    let toast =
        document.getElementById(
            "finflow-toast"
        );

    if (!toast) {

        toast =
            document.createElement("div");

        toast.id =
            "finflow-toast";

        toast.className =
            "finflow-toast";

        document.body.appendChild(toast);
    }

    toast.textContent = message;

    toast.dataset.type = type;

    toast.classList.add("show");

    clearTimeout(
        window.finflowToastTimer
    );

    window.finflowToastTimer =
        setTimeout(
            () => {

                toast.classList.remove(
                    "show"
                );

            },
            3000
        );
}


async function fetchJSON(
    url,
    options = {}
) {

    const response =
        await fetch(
            url,
            options
        );

    let data = null;

    try {

        data =
            await response.json();

    } catch {

        data = {};

    }

    if (!response.ok) {

        throw new Error(
            data.message ||
            data.error ||
            `Request failed (${response.status})`
        );
    }

    return data;
}


const navItems =
    document.querySelectorAll(
        ".nav-item"
    );

const pages =
    document.querySelectorAll(
        ".page-view"
    );


function showPage(viewName) {

    navItems.forEach(
        item => {

            item.classList.toggle(
                "active",
                item.dataset.view === viewName
            );

        }
    );


    pages.forEach(
        page => {

            page.classList.toggle(
                "active-view",
                page.id === `${viewName}-view`
            );

        }
    );


    if (viewName === "home") {

        loadDashboard();

        loadCharts();

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


navItems.forEach(
    item => {

        item.addEventListener(
            "click",
            () => {

                showPage(
                    item.dataset.view
                );

            }
        );

    }
);


const viewInsightsButton =
    document.getElementById(
        "view-insights-btn"
    );


if (viewInsightsButton) {

    viewInsightsButton.addEventListener(
        "click",
        () => {

            showPage(
                "coach"
            );

        }
    );

}


function openModal(modalId) {

    const modal =
        document.getElementById(
            modalId
        );

    if (!modal) return;

    modal.hidden = false;

    document.body.classList.add(
        "modal-open"
    );

}


function closeModal(modalId) {

    const modal =
        document.getElementById(
            modalId
        );

    if (!modal) return;

    modal.hidden = true;

    const anyOpenModal =
        document.querySelector(
            ".modal-overlay:not([hidden])"
        );

    if (!anyOpenModal) {

        document.body.classList.remove(
            "modal-open"
        );

    }

}


document.addEventListener(
    "click",
    event => {

        const closeButton =
            event.target.closest(
                "[data-close-modal]"
            );

        if (closeButton) {

            closeModal(
                closeButton.dataset.closeModal
            );

        }


        if (
            event.target.classList.contains(
                "modal-overlay"
            )
        ) {

            closeModal(
                event.target.id
            );

        }

    }
);


document.addEventListener(
    "keydown",
    event => {

        if (event.key !== "Escape") {
            return;
        }

        document
            .querySelectorAll(
                ".modal-overlay:not([hidden])"
            )
            .forEach(
                modal => {

                    closeModal(
                        modal.id
                    );

                }
            );

    }
);


const addTransactionButton =
    document.getElementById(
        "add-transaction-btn"
    );


if (addTransactionButton) {

    addTransactionButton.addEventListener(
        "click",
        () => {

            openModal(
                "transaction-modal"
            );

        }
    );

}


const coachAddTransactionButton =
    document.getElementById(
        "coach-add-transaction-btn"
    );


if (coachAddTransactionButton) {

    coachAddTransactionButton.addEventListener(
        "click",
        () => {

            openModal(
                "transaction-modal"
            );

        }
    );

}


const transactionForm =
    document.getElementById(
        "transaction-form"
    );


if (transactionForm) {

    transactionForm.addEventListener(
        "submit",
        async event => {

            event.preventDefault();

            const formData =
                new FormData(
                    transactionForm
                );

            const payload = {

                type:
                    formData.get(
                        "type"
                    ),

                amount:
                    Number(
                        formData.get(
                            "amount"
                        )
                    ),

                category:
                    formData.get(
                        "category"
                    ),

                description:
                    formData.get(
                        "description"
                    ) || "",

                date:
                    formData.get(
                        "date"
                    )

            };


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
                                JSON.stringify(
                                    payload
                                )
                        }
                    );


                showToast(
                    result.message ||
                    "Transaction added successfully.",
                    "success"
                );


                transactionForm.reset();


                const dateInput =
                    document.getElementById(
                        "transaction-date"
                    );


                if (dateInput) {

                    dateInput.value =
                        getTodayString();

                }


                closeModal(
                    "transaction-modal"
                );


                await refreshAll();

            } catch (error) {

                console.error(
                    "Transaction error:",
                    error
                );

                showToast(
                    error.message ||
                    "Unable to add transaction.",
                    "error"
                );

            }

        }
    );

}


let allTransactions = [];

let currentTransactionFilter =
    "all";


async function loadTransactions() {

    try {

        const data =
            await fetchJSON(
                "/api/transactions"
            );


        allTransactions =
            Array.isArray(data)
                ? data
                : [];


        renderTransactions();

    } catch (error) {

        console.error(
            "Transaction loading error:",
            error
        );

    }

}


function renderTransactions() {

    const tbody =
        document.getElementById(
            "transaction-table-body"
        );

    if (!tbody) return;


    const searchInput =
        document.getElementById(
            "transaction-search"
        );


    const search =
        searchInput
            ? searchInput.value
                .trim()
                .toLowerCase()
            : "";


    let transactions =
        [...allTransactions];


    if (
        currentTransactionFilter !==
        "all"
    ) {

        transactions =
            transactions.filter(
                transaction =>
                    transaction.type ===
                    currentTransactionFilter
            );

    }


    if (search) {

        transactions =
            transactions.filter(
                transaction => {

                    const text = [

                        transaction.description,

                        transaction.category,

                        transaction.type,

                        transaction.date

                    ]
                        .join(" ")
                        .toLowerCase();

                    return text.includes(
                        search
                    );

                }
            );

    }


    if (!transactions.length) {

        tbody.innerHTML = `

            <tr>

                <td colspan="5">

                    No transactions found.

                </td>

            </tr>

        `;

        return;

    }


    tbody.innerHTML =
        transactions
            .map(
                transaction => {

                    const isIncome =
                        transaction.type ===
                        "income";


                    const amount =
                        Number(
                            transaction.amount ||
                            0
                        );


                    return `

                        <tr>

                            <td>
                                ${escapeHTML(
                                    transaction.date ||
                                    ""
                                )}
                            </td>

                            <td>
                                ${escapeHTML(
                                    transaction.description ||
                                    "Transaction"
                                )}
                            </td>

                            <td>
                                ${escapeHTML(
                                    transaction.category ||
                                    "Other"
                                )}
                            </td>

                            <td>
                                ${escapeHTML(
                                    transaction.type ||
                                    ""
                                )}
                            </td>

                            <td class="${
                                isIncome
                                    ? "amount-income"
                                    : "amount-expense"
                            }">

                                ${
                                    isIncome
                                        ? "+"
                                        : "-"
                                }${formatMoney(amount)}

                            </td>

                        </tr>

                    `;

                }
            )
            .join("");

}


const transactionSearch =
    document.getElementById(
        "transaction-search"
    );


if (transactionSearch) {

    transactionSearch.addEventListener(
        "input",
        renderTransactions
    );

}


document
    .querySelectorAll(
        ".filter-tab"
    )
    .forEach(
        button => {

            button.addEventListener(
                "click",
                () => {

                    document
                        .querySelectorAll(
                            ".filter-tab"
                        )
                        .forEach(
                            tab =>
                                tab.classList.remove(
                                    "active"
                                )
                        );


                    button.classList.add(
                        "active"
                    );


                    currentTransactionFilter =
                        button.dataset.filter ||
                        "all";


                    renderTransactions();

                }
            );

        }
    );


async function loadDashboard() {

    try {

        const data =
            await fetchJSON(
                "/api/dashboard"
            );


        const summary =
            data.summary || {};


        setText(
            "balance-value",
            formatMoney(
                summary.balance || 0
            )
        );


        setText(
            "income-value",
            formatMoney(
                summary.income || 0
            )
        );


        setText(
            "expense-value",
            formatMoney(
                summary.expenses || 0
            )
        );


        setText(
            "savings-value",
            `${Number(
                summary.savings_rate || 0
            ).toFixed(0)}%`
        );


        const recent =
            data.recent_transactions || [];


        renderRecentTransactions(
            recent
        );


        renderHomeBudgetProgress();

        loadRecurringExpenses();

    } catch (error) {

        console.error(
            "Dashboard error:",
            error
        );

    }

}


function setText(
    id,
    value
) {

    const element =
        document.getElementById(
            id
        );

    if (element) {

        element.textContent =
            value;

    }

}


function renderRecentTransactions(
    transactions
) {

    const container =
        document.getElementById(
            "recent-transactions"
        );

    if (!container) return;


    if (!transactions.length) {

        container.innerHTML = `

            <div class="empty-state">

                <p>
                    No recent transactions.
                </p>

            </div>

        `;

        return;

    }


    container.innerHTML =
        transactions
            .map(
                transaction => {

                    const income =
                        transaction.type ===
                        "income";


                    return `

                        <div class="recent-transaction">

                            <div>

                                <strong>
                                    ${escapeHTML(
                                        transaction.description ||
                                        "Transaction"
                                    )}
                                </strong>

                                <span>
                                    ${escapeHTML(
                                        transaction.category ||
                                        "Other"
                                    )}
                                </span>

                            </div>

                            <strong class="${
                                income
                                    ? "amount-income"
                                    : "amount-expense"
                            }">

                                ${
                                    income
                                        ? "+"
                                        : "-"
                                }${formatMoney(
                                    transaction.amount
                                )}

                            </strong>

                        </div>

                    `;

                }
            )
            .join("");

}


let incomeExpenseChart = null;

let spendingChart = null;


function populateYearSelectors() {

    const currentYear =
        new Date().getFullYear();


    const selectors = [

        document.getElementById(
            "cashflow-year"
        ),

        document.getElementById(
            "spending-year"
        )

    ];


    selectors.forEach(
        select => {

            if (!select) return;


            select.innerHTML = "";


            for (
                let year =
                    currentYear - 5;

                year <=
                currentYear + 1;

                year++
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
                    year ===
                    currentYear
                ) {

                    option.selected =
                        true;

                }

                select.appendChild(
                    option
                );

            }

        }
    );

}


function setInitialMonthSelectors() {

    const currentMonth =
        new Date().getMonth() + 1;


    const spendingMonth =
        document.getElementById(
            "spending-month"
        );


    if (spendingMonth) {

        spendingMonth.value =
            currentMonth;

    }


    const cashflowMonth =
        document.getElementById(
            "cashflow-month"
        );


    if (cashflowMonth) {

        cashflowMonth.value =
            "all";

    }

}


async function loadCharts() {

    await loadIncomeExpenseChart();

    await loadSpendingChart();

}


async function loadIncomeExpenseChart() {

    const canvas =
        document.getElementById(
            "income-expense-chart"
        );


    if (!canvas) return;


    try {

        const year =
            document.getElementById(
                "cashflow-year"
            )?.value ||
            new Date().getFullYear();


        const data =
            await fetchJSON(
                `/api/monthly-summary?year=${year}`
            );


        const labels =
            data.map(
                item =>
                    item.month_name
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

                        labels,

                        datasets: [

                            {
                                label: "Income",
                                data: income,
                                borderRadius: 6
                            },

                            {
                                label: "Expenses",
                                data: expenses,
                                borderRadius: 6
                            }

                        ]

                    },

                    options: {

                        responsive: true,

                        maintainAspectRatio: false,

                        plugins: {

                            legend: {
                                display: true
                            }

                        },

                        scales: {

                            y: {

                                beginAtZero: true,

                                ticks: {

                                    callback:
                                        value =>
                                            "₹" +
                                            Number(
                                                value
                                            ).toLocaleString(
                                                "en-IN"
                                            )

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


async function loadSpendingChart() {

    const canvas =
        document.getElementById(
            "spending-chart"
        );


    if (!canvas) return;


    try {

        const month =
            document.getElementById(
                "spending-month"
            )?.value;


        const year =
            document.getElementById(
                "spending-year"
            )?.value ||
            new Date().getFullYear();


        const data =
            await fetchJSON(
                `/api/spending-by-category?year=${year}&month=${month}`
            );


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


        setText(
            "spending-total",
            formatMoney(total)
        );


        if (spendingChart) {

            spendingChart.destroy();

        }


        spendingChart =
            new Chart(
                canvas,
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

                        cutout: "65%",

                        plugins: {

                            legend: {

                                display: true,

                                position: "right"

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


document
    .getElementById(
        "cashflow-year"
    )
    ?.addEventListener(
        "change",
        loadIncomeExpenseChart
    );


document
    .getElementById(
        "spending-month"
    )
    ?.addEventListener(
        "change",
        loadSpendingChart
    );


document
    .getElementById(
        "spending-year"
    )
    ?.addEventListener(
        "change",
        loadSpendingChart
    );


async function loadBudgets() {

    try {

        const data =
            await fetchJSON(
                "/api/budgets"
            );


        renderBudgetList(
            data
        );


        await renderHomeBudgetProgress();

    } catch (error) {

        console.error(
            "Budget loading error:",
            error
        );

    }

}


function renderBudgetList(
    budgets
) {

    const container =
        document.getElementById(
            "budget-list"
        );


    if (!container) return;


    if (!budgets.length) {

        container.innerHTML = `

            <div class="empty-state">

                <p>
                    No budgets created yet.
                </p>

                <button
                    class="primary-button"
                    id="empty-create-budget-btn"
                    type="button"
                >
                    + Create Budget
                </button>

            </div>

        `;

        document
            .getElementById(
                "empty-create-budget-btn"
            )
            ?.addEventListener(
                "click",
                () =>
                    openModal(
                        "budget-modal"
                    )
            );

        return;

    }


    container.innerHTML =
        budgets
            .map(
                budget => `

                    <div class="budget-item">

                        <div class="budget-item-header">

                            <strong>
                                ${escapeHTML(
                                    budget.category
                                )}
                            </strong>

                            <span>
                                ${formatMoney(
                                    budget.amount
                                )}
                            </span>

                        </div>

                    </div>

                `
            )
            .join("");

}


async function renderHomeBudgetProgress() {

    const container =
        document.getElementById(
            "home-budget-progress"
        );


    if (!container) return;


    try {

        const data =
            await fetchJSON(
                "/api/budget-progress"
            );


        if (!data.length) {

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
            data
                .slice(0, 4)
                .map(
                    budget => {

                        const percentage =
                            Math.min(
                                Number(
                                    budget.percentage ||
                                    0
                                ),
                                100
                            );


                        return `

                            <div class="budget-preview-item">

                                <div class="budget-preview-header">

                                    <strong>
                                        ${escapeHTML(
                                            budget.category
                                        )}
                                    </strong>

                                    <span>
                                        ${formatMoney(
                                            budget.spent
                                        )} /
                                        ${formatMoney(
                                            budget.budget
                                        )}
                                    </span>

                                </div>

                                <div class="progress-track">

                                    <div
                                        class="progress-fill"
                                        style="width:${percentage}%"
                                    ></div>

                                </div>

                            </div>

                        `;

                    }
                )
                .join("");

    } catch (error) {

        console.error(
            "Budget progress error:",
            error
        );

    }

}


const createBudgetButton =
    document.getElementById(
        "create-budget-btn"
    );


if (createBudgetButton) {

    createBudgetButton.addEventListener(
        "click",
        () =>
            openModal(
                "budget-modal"
            )
    );

}


const budgetForm =
    document.getElementById(
        "budget-form"
    );


if (budgetForm) {

    budgetForm.addEventListener(
        "submit",
        async event => {

            event.preventDefault();

            const formData =
                new FormData(
                    budgetForm
                );


            const payload = {

                category:
                    formData.get(
                        "category"
                    ),

                amount:
                    Number(
                        formData.get(
                            "amount"
                        )
                    )

            };


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
                                JSON.stringify(
                                    payload
                                )

                        }
                    );


                showToast(
                    result.message ||
                    "Budget saved.",
                    "success"
                );


                budgetForm.reset();

                closeModal(
                    "budget-modal"
                );

                await refreshAll();

            } catch (error) {

                showToast(
                    error.message ||
                    "Unable to save budget.",
                    "error"
                );

            }

        }
    );

}


async function loadGoals() {

    try {

        const data =
            await fetchJSON(
                "/api/goal-progress"
            );


        renderGoals(
            data
        );

    } catch (error) {

        console.error(
            "Goal loading error:",
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


    if (!container) return;


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
                    id="empty-create-goal-btn"
                    type="button"
                >
                    + Create Goal
                </button>

            </article>

        `;


        document
            .getElementById(
                "empty-create-goal-btn"
            )
            ?.addEventListener(
                "click",
                () =>
                    openModal(
                        "goal-modal"
                    )
            );

        return;

    }


    container.innerHTML =
        goals
            .map(
                goal => {

                    const percentage =
                        Math.min(
                            Number(
                                goal.percentage ||
                                0
                            ),
                            100
                        );


                    return `

                        <article class="dashboard-card goal-card">

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

                            <div class="progress-track">

                                <div
                                    class="progress-fill"
                                    style="width:${percentage}%"
                                ></div>

                            </div>

                            <p>
                                ${formatMoney(
                                    goal.current
                                )}
                                of
                                ${formatMoney(
                                    goal.target
                                )}
                            </p>

                            <strong>
                                ${percentage.toFixed(0)}%
                            </strong>

                        </article>

                    `;

                }
            )
            .join("");

}


const createGoalButton =
    document.getElementById(
        "create-goal-btn"
    );


if (createGoalButton) {

    createGoalButton.addEventListener(
        "click",
        () =>
            openModal(
                "goal-modal"
            )
    );

}


const goalPreset =
    document.getElementById(
        "goal-name-select"
    );


const customGoalGroup =
    document.getElementById(
        "custom-goal-group"
    );


if (goalPreset) {

    goalPreset.addEventListener(
        "change",
        () => {

            if (customGoalGroup) {

                customGoalGroup.hidden =
                    goalPreset.value !==
                    "custom";

            }

        }
    );

}


const goalForm =
    document.getElementById(
        "goal-form"
    );


if (goalForm) {

    goalForm.addEventListener(
        "submit",
        async event => {

            event.preventDefault();


            const formData =
                new FormData(
                    goalForm
                );


            const preset =
                formData.get(
                    "goalPreset"
                );


            const customName =
                formData.get(
                    "name"
                );


            const name =
                preset &&
                preset !== "custom"
                    ? preset
                    : customName;


            const payload = {

                name:
                    name,

                target:
                    Number(
                        formData.get(
                            "target"
                        )
                    ),

                current:
                    Number(
                        formData.get(
                            "current"
                        ) || 0
                    ),

                deadline:
                    formData.get(
                        "deadline"
                    ) || null

            };


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
                                JSON.stringify(
                                    payload
                                )

                        }
                    );


                showToast(
                    result.message ||
                    "Goal created.",
                    "success"
                );


                goalForm.reset();

                if (customGoalGroup) {
                    customGoalGroup.hidden =
                        true;
                }

                closeModal(
                    "goal-modal"
                );

                await refreshAll();

            } catch (error) {

                showToast(
                    error.message ||
                    "Unable to create goal.",
                    "error"
                );

            }

        }
    );

}


async function loadRecurringExpenses() {

    try {

        const data =
            await fetchJSON(
                "/api/recurring"
            );


        const items =
            data.items || [];


        const container =
            document.getElementById(
                "home-recurring-expenses"
            );


        const summary =
            document.getElementById(
                "home-recurring-summary"
            );


        if (summary) {

            summary.textContent =
                `${data.count || 0} recurring payments · ${formatMoney(
                    data.monthly_total || 0
                )}/month`;

        }


        if (!container) return;


        if (!items.length) {

            container.innerHTML = `

                <div class="insight-item">

                    <span>🔄</span>

                    <div>

                        <strong>
                            No recurring expenses detected
                        </strong>

                        <p>
                            Regular payments will appear here when FinFlow detects them.
                        </p>

                    </div>

                </div>

            `;

            return;

        }


        container.innerHTML =
            items
                .slice(0, 4)
                .map(
                    item => `

                        <div class="recurring-item">

                            <div class="recurring-item-main">

                                <strong>
                                    ${escapeHTML(
                                        item.description ||
                                        "Recurring expense"
                                    )}
                                </strong>

                                <span>
                                    ${escapeHTML(
                                        item.frequency ||
                                        "Recurring"
                                    )}
                                </span>

                            </div>

                            <strong>
                                ${formatMoney(
                                    item.amount ||
                                    item.estimated_monthly ||
                                    0
                                )}
                            </strong>

                        </div>

                    `
                )
                .join("");

    } catch (error) {

        console.error(
            "Recurring expenses error:",
            error
        );

    }

}


function setUploadStatus(
    title,
    message,
    state = "info",
    stats = null
) {

    const card =
        document.getElementById(
            "upload-status-card"
        );


    const titleElement =
        document.getElementById(
            "upload-status-title"
        );


    const messageElement =
        document.getElementById(
            "upload-status-message"
        );


    const icon =
        document.getElementById(
            "upload-status-icon"
        );


    const imported =
        document.getElementById(
            "upload-imported-count"
        );


    const categorized =
        document.getElementById(
            "upload-categorized-count"
        );


    const review =
        document.getElementById(
            "upload-review-count"
        );


    if (!card) {
        return;
    }


    card.hidden =
        false;


    card.dataset.state =
        state;


    if (titleElement) {

        titleElement.textContent =
            title;

    }


    if (messageElement) {

        messageElement.textContent =
            message;

    }


    if (icon) {

        icon.textContent =

            state === "success"
                ? "✓"

                :

            state === "error"
                ? "!"

                :

            state === "loading"
                ? "…"

                :

                "i";

    }


    if (stats) {

        if (imported) {

            imported.textContent =
                stats.imported ??
                0;

        }


        if (categorized) {

            categorized.textContent =
                stats.categorized ??
                stats.auto_categorized ??
                0;

        }


        if (review) {

            review.textContent =
                stats.review ??
                stats.needs_review ??
                0;

        }

    }

}


const uploadStatementButton =
    document.getElementById(
        "upload-statement-btn"
    );


const statementFile =
    document.getElementById(
        "statement-file"
    );


if (uploadStatementButton) {

    uploadStatementButton.addEventListener(
        "click",
        () => {

            statementFile?.click();

        }
    );

}


if (statementFile) {

    statementFile.addEventListener(
        "change",
        async () => {

            const file =
                statementFile.files?.[0];


            if (!file) {
                return;
            }


            const formData =
                new FormData();


            formData.append(
                "file",
                file
            );


            setUploadStatus(
                "Processing statement",
                "FinFlow is reading your statement...",
                "loading"
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


                setUploadStatus(
                    "Statement imported",
                    result.message ||
                    "Transactions imported successfully.",
                    "success",
                    result
                );


                showToast(
                    result.message ||
                    "Statement imported.",
                    "success"
                );


                statementFile.value =
                    "";


                await refreshAll();

            } catch (error) {

                console.error(
                    "Statement upload error:",
                    error
                );


                setUploadStatus(
                    "Import failed",
                    error.message ||
                    "Could not process the statement.",
                    "error"
                );


                showToast(
                    error.message ||
                    "Statement import failed.",
                    "error"
                );

            }

        }
    );

}


let aiConfigured =
    false;

let speechRecognition =
    null;

let isListening =
    false;


function formatAIResponse(
    message
) {

    const fragment =
        document.createDocumentFragment();


    const source =
        String(
            message || ""
        )
            .replace(
                /\r/g,
                ""
            )
            .trim();


    if (!source) {

        const p =
            document.createElement(
                "p"
            );

        p.textContent =
            "I could not generate a response.";

        fragment.appendChild(
            p
        );

        return fragment;

    }


    const lines =
        source.split(
            "\n"
        );


    let currentList =
        null;


    function finishList() {

        if (currentList) {

            fragment.appendChild(
                currentList
            );

            currentList =
                null;

        }

    }


    function appendInline(
        parent,
        value
    ) {

        const parts =
            String(value).split(
                /(\*\*[^*]+\*\*|__[^_]+__)/
            );


        parts.forEach(
            part => {

                if (!part) {
                    return;
                }


                const boldMatch =
                    part.match(
                        /^\*\*(.+)\*\*$/
                    ) ||
                    part.match(
                        /^__(.+)__?$/
                    );


                if (boldMatch) {

                    const strong =
                        document.createElement(
                            "strong"
                        );


                    strong.textContent =
                        boldMatch[1];


                    parent.appendChild(
                        strong
                    );

                } else {

                    parent.appendChild(
                        document.createTextNode(
                            part
                        )
                    );

                }

            }
        );

    }


    lines.forEach(
        rawLine => {

            const line =
                rawLine.trim();


            if (!line) {

                finishList();

                return;

            }


            const headingMatch =
                line.match(
                    /^#{1,3}\s+(.+)$/
                );


            const boldHeadingMatch =
                line.match(
                    /^\*\*(.+)\*\*:?\s*$/
                );


            if (
                headingMatch ||
                boldHeadingMatch
            ) {

                finishList();


                const heading =
                    document.createElement(
                        "strong"
                    );


                heading.className =
                    "ai-response-heading";


                heading.textContent =
                    (
                        headingMatch
                            ? headingMatch[1]
                            : boldHeadingMatch[1]
                    )
                        .replace(
                            /:$/,
                            ""
                        );


                fragment.appendChild(
                    heading
                );


                return;

            }


            const bulletMatch =
                line.match(
                    /^(?:[-*•]|\d+[.)])\s+(.+)$/
                );


            if (bulletMatch) {

                if (!currentList) {

                    currentList =
                        document.createElement(
                            "ul"
                        );

                    currentList.className =
                        "ai-response-list";

                }


                const item =
                    document.createElement(
                        "li"
                    );


                appendInline(
                    item,
                    bulletMatch[1]
                );


                currentList.appendChild(
                    item
                );


                return;

            }


            finishList();


            const paragraph =
                document.createElement(
                    "p"
                );


            appendInline(
                paragraph,
                line
            );


            fragment.appendChild(
                paragraph
            );

        }
    );


    finishList();


    return fragment;

}


function addAIMessage(
    message,
    role = "assistant"
) {

    const container =
        document.getElementById(
            "ai-chat-messages"
        );


    if (!container) {
        return;
    }


    const bubble =
        document.createElement(
            "div"
        );


    bubble.className =
        `ai-message ${role}`;


    const label =
        document.createElement(
            "span"
        );


    label.className =
        "ai-message-label";


    label.textContent =
        role === "user"
            ? "You"
            : "FinFlow AI";


    bubble.appendChild(
        label
    );


    if (
        role ===
        "assistant"
    ) {

        bubble.appendChild(
            formatAIResponse(
                message
            )
        );

    } else {

        const text =
            document.createElement(
                "p"
            );


        text.textContent =
            String(
                message || ""
            );


        bubble.appendChild(
            text
        );

    }


    container.appendChild(
        bubble
    );


    container.scrollTop =
        container.scrollHeight;

}


function setAIStatus(
    text,
    state = "info"
) {

    const badge =
        document.getElementById(
            "ai-status-badge"
        );


    const status =
        document.getElementById(
            "ai-chat-status"
        );


    if (badge) {

        badge.textContent =
            text;

        badge.dataset.state =
            state;

    }


    if (status) {

        status.textContent =
            text;

        status.dataset.state =
            state;

    }

}


async function checkAIStatus() {

    try {

        const data =
            await fetchJSON(
                "/api/ai/status"
            );


        aiConfigured =
            Boolean(
                data.configured
            );


        if (aiConfigured) {

            setAIStatus(
                "AI Connected",
                "success"
            );

        } else {

            setAIStatus(
                "AI Not Connected",
                "error"
            );

        }

    } catch (error) {

        aiConfigured =
            false;


        setAIStatus(
            "AI Unavailable",
            "error"
        );


        console.error(
            "AI status error:",
            error
        );

    }

}


async function sendAIMessage(
    message
) {

    const question =
        String(
            message || ""
        ).trim();


    if (!question) {
        return;
    }


    addAIMessage(
        question,
        "user"
    );


    const input =
        document.getElementById(
            "ai-chat-input"
        );


    const sendButton =
        document.getElementById(
            "ai-send-btn"
        );


    if (input) {

        input.value =
            "";

    }


    if (sendButton) {

        sendButton.disabled =
            true;

    }


    setAIStatus(
        "Thinking...",
        "loading"
    );


    try {

        const result =
            await fetchJSON(
                "/api/ai/chat",
                {

                    method: "POST",

                    headers: {

                        "Content-Type":
                            "application/json"

                    },

                    body:
                        JSON.stringify(
                            {
                                message:
                                    question
                            }
                        )

                }
            );


        if (!result.success) {

            throw new Error(
                result.message ||
                "AI could not answer."
            );

        }


        addAIMessage(
            result.reply ||
            "I could not generate a response.",
            "assistant"
        );


        setAIStatus(
            "AI Connected",
            "success"
        );

    } catch (error) {

        console.error(
            "AI chat error:",
            error
        );


        addAIMessage(
            error.message ||
            "AI request failed.",
            "assistant"
        );


        setAIStatus(
            "AI Error",
            "error"
        );

    } finally {

        if (sendButton) {

            sendButton.disabled =
                false;

        }

    }

}


function setupVoiceInput() {

    const voiceButton =
        document.getElementById(
            "ai-voice-btn"
        );


    const input =
        document.getElementById(
            "ai-chat-input"
        );


    if (
        !voiceButton ||
        !input
    ) {

        return;

    }


    const Recognition =
        window.SpeechRecognition ||
        window.webkitSpeechRecognition;


    if (!Recognition) {

        voiceButton.disabled =
            true;

        voiceButton.title =
            "Voice input is not supported by this browser.";

        return;

    }


    speechRecognition =
        new Recognition();


    speechRecognition.continuous =
        false;


    speechRecognition.interimResults =
        false;


    speechRecognition.lang =
        "en-IN";


    speechRecognition.onstart =
        () => {

            isListening =
                true;

            voiceButton.classList.add(
                "listening"
            );

            setAIStatus(
                "Listening...",
                "loading"
            );

        };


    speechRecognition.onresult =
        event => {

            const transcript =
                event.results?.[0]?.[0]?.transcript ||
                "";


            input.value =
                transcript;


            setAIStatus(
                "Voice captured",
                "success"
            );


            input.focus();

        };


    speechRecognition.onerror =
        event => {

            console.error(
                "Voice input error:",
                event.error
            );


            setAIStatus(
                "Voice input failed",
                "error"
            );

        };


    speechRecognition.onend =
        () => {

            isListening =
                false;

            voiceButton.classList.remove(
                "listening"
            );

        };


    voiceButton.addEventListener(
        "click",
        () => {

            if (isListening) {

                speechRecognition.stop();

                return;

            }


            try {

                speechRecognition.start();

            } catch (error) {

                console.error(
                    "Could not start voice input:",
                    error
                );

            }

        }
    );

}


function setupAIChat() {

    const form =
        document.getElementById(
            "ai-chat-form"
        );


    const input =
        document.getElementById(
            "ai-chat-input"
        );


    if (form) {

        form.addEventListener(
            "submit",
            event => {

                event.preventDefault();

                sendAIMessage(
                    input
                        ? input.value
                        : ""
                );

            }
        );

    }


    setupVoiceInput();

}


async function loadSmartCoach() {

    try {

        const data =
            await fetchJSON(
                "/api/financial-health"
            );


        if (
            data &&
            typeof data ===
                "object"
        ) {

            if (
                data.score !==
                undefined
            ) {

                setText(
                    "financial-health-score",
                    Number(
                        data.score
                    ).toFixed(0)
                );

            }


            if (
                data.status
            ) {

                setText(
                    "financial-health-status",
                    data.status
                );

            }

        }

    } catch (error) {

        console.error(
            "Smart Coach loading error:",
            error
        );

    }

}


function setupProfileAndBottomNavigation() {

    const profileNameElement =
        document.getElementById(
            "profile-menu-name"
        );


    const profileAvatar =
        document.getElementById(
            "profile-avatar"
        );


    const profileAvatarMenu =
        document.getElementById(
            "profile-avatar-menu"
        );


    const profileInput =
        document.getElementById(
            "profile-name-input"
        );


    const profileHeaderName =
        document.querySelector(
            "#home-view .page-header h2"
        );


    function getProfileName() {

        return (
            localStorage.getItem(
                "finflow_profile_name"
            ) ||
            "Saad"
        );

    }


    function getInitials(
        name
    ) {

        const parts =
            String(
                name ||
                "Saad"
            )
                .trim()
                .split(
                    /\s+/
                )
                .filter(
                    Boolean
                );


        if (!parts.length) {

            return "S";

        }


        if (
            parts.length ===
            1
        ) {

            return parts[0]
                .charAt(0)
                .toUpperCase();

        }


        return (

            parts[0]
                .charAt(0) +

            parts[
                parts.length - 1
            ]
                .charAt(0)

        ).toUpperCase();

    }


    function updateProfileDisplay() {

        const name =
            getProfileName();


        const initials =
            getInitials(
                name
            );


        if (profileNameElement) {

            profileNameElement.textContent =
                name;

        }


        if (profileAvatar) {

            profileAvatar.textContent =
                initials;

        }


        if (profileAvatarMenu) {

            profileAvatarMenu.textContent =
                initials;

        }


        if (profileInput) {

            profileInput.value =
                name;

        }


        if (profileHeaderName) {

            profileHeaderName.textContent =
                `Good Morning, ${name}! 👋`;

        }

    }


    updateProfileDisplay();


    const profileTrigger =
        document.getElementById(
            "profile-trigger"
        );


    const profileMenu =
        document.getElementById(
            "profile-menu"
        );


    const profileButton =
        document.getElementById(
            "bottom-profile-btn"
        );


    if (profileTrigger) {

        profileTrigger.addEventListener(
            "keydown",
            event => {

                if (
                    event.key ===
                    "Escape" &&
                    profileMenu
                ) {

                    profileMenu.hidden =
                        true;


                    profileTrigger.setAttribute(
                        "aria-expanded",
                        "false"
                    );

                }

            }
        );

    }


    const bottomButtons =
        document.querySelectorAll(
            ".bottom-nav-item"
        );


    function setBottomActive(
        buttonId
    ) {

        bottomButtons.forEach(
            button => {

                button.classList.toggle(
                    "active",
                    button.id ===
                        buttonId
                );

            }
        );

    }


    const homeButton =
        document.getElementById(
            "bottom-home-btn"
        );


    const analyticsButton =
        document.getElementById(
            "bottom-analytics-btn"
        );


    const addButton =
        document.getElementById(
            "bottom-add-transaction-btn"
        );


    const historyButton =
        document.getElementById(
            "bottom-history-btn"
        );


    if (homeButton) {

        homeButton.addEventListener(
            "click",
            () => {

                if (
                    typeof showPage ===
                    "function"
                ) {

                    showPage(
                        "home"
                    );

                }


                setBottomActive(
                    "bottom-home-btn"
                );


                window.scrollTo(
                    {
                        top: 0,
                        behavior:
                            "smooth"
                    }
                );

            }
        );

    }


    if (analyticsButton) {

        analyticsButton.addEventListener(
            "click",
            () => {

                if (
                    typeof showPage ===
                    "function"
                ) {

                    showPage(
                        "home"
                    );

                }


                setBottomActive(
                    "bottom-analytics-btn"
                );


                const chart =
                    document.getElementById(
                        "income-expense-chart"
                    );


                if (chart) {

                    const card =
                        chart.closest(
                            ".dashboard-card"
                        );


                    if (card) {

                        setTimeout(
                            () => {

                                card.scrollIntoView(
                                    {
                                        behavior:
                                            "smooth",
                                        block:
                                            "start"
                                    }
                                );

                            },
                            50
                        );

                    }

                }

            }
        );

    }


    if (addButton) {

        addButton.addEventListener(
            "click",
            () => {

                if (
                    typeof openModal ===
                    "function"
                ) {

                    openModal(
                        "transaction-modal"
                    );

                } else {

                    console.error(
                        "openModal is not available."
                    );

                }

            }
        );

    }