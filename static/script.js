const navItems = document.querySelectorAll(".nav-item");
const pages = document.querySelectorAll(".page-view");

navItems.forEach(item => {

    item.addEventListener("click", () => {

        const view = item.dataset.view;

        navItems.forEach(nav => {
            nav.classList.remove("active");
        });

        item.classList.add("active");

        pages.forEach(page => {
            page.classList.remove("active-view");
        });

        document
            .getElementById(`${view}-view`)
            .classList.add("active-view");

    });

});

async function loadDashboard() {

    const response = await fetch("/api/dashboard");
    const data = await response.json();

    const cards = document.querySelectorAll(
        "#home-view .stat-card h3"
    );

    if (cards.length >= 4) {

        cards[0].textContent =
            `₹${data.summary.balance.toFixed(2)}`;

        cards[1].textContent =
            `₹${data.summary.income.toFixed(2)}`;

        cards[2].textContent =
            `₹${data.summary.expenses.toFixed(2)}`;

        cards[3].textContent =
            `${data.summary.savings_rate.toFixed(1)}%`;
    }

}

let transactions = [];

async function loadTransactions() {

    const response =
        await fetch("/api/transactions");

    transactions =
        await response.json();

    displayTransactions(transactions);
}


function displayTransactions(data) {

    const table =
        document.querySelector(
            ".transaction-table tbody"
        );

    if (!table) return;

    if (data.length === 0) {

        table.innerHTML = `
            <tr>
                <td colspan="5">
                    No transactions yet
                </td>
            </tr>
        `;

        return;
    }


    table.innerHTML = data.map(transaction => {

        const sign =
            transaction.type === "income"
                ? "+"
                : "-";

        return `
            <tr>
                <td>${transaction.date}</td>
                <td>${transaction.description || "—"}</td>
                <td>${transaction.category}</td>
                <td>${transaction.type}</td>
                <td>${sign}₹${Number(transaction.amount).toFixed(2)}</td>
            </tr>
        `;

    }).join("");

}

const searchBox =
    document.querySelector(
        ".search-box input"
    );

if (searchBox) {

    searchBox.addEventListener(
        "input",
        () => {

            const text =
                searchBox.value.toLowerCase();

            const filtered =
                transactions.filter(transaction =>
                    (
                        transaction.description || ""
                    )
                    .toLowerCase()
                    .includes(text)
                );

            displayTransactions(filtered);

        }
    );

}

const filterButtons =
    document.querySelectorAll(
        ".filter-tab"
    );

filterButtons.forEach(button => {

    button.addEventListener("click", () => {

        filterButtons.forEach(btn =>
            btn.classList.remove("active")
        );

        button.classList.add("active");

        const filter =
            button.textContent
                .trim()
                .toLowerCase();

        if (filter === "all") {

            displayTransactions(
                transactions
            );

        } else {

            displayTransactions(
                transactions.filter(
                    transaction =>
                        transaction.type === filter
                )
            );

        }

    });

});

const addButtons =
    document.querySelectorAll(
        ".primary-button"
    );

addButtons.forEach(button => {

    if (
        button.textContent
            .toLowerCase()
            .includes("add transaction")
    ) {

        button.addEventListener(
            "click",
            addTransaction
        );

    }

});


async function addTransaction() {

    const type =
        prompt(
            "Type: income or expense"
        );

    if (!type) return;


    const amount =
        prompt("Enter amount:");

    if (!amount) return;


    const category =
        prompt(
            "Category (Food, Transport, Shopping, Education, Bills, Entertainment, Health, Salary, Other):"
        );


    const description =
        prompt(
            "Description (optional):"
        );


    const date =
        prompt(
            "Date (YYYY-MM-DD):"
        );


    const response =
        await fetch(
            "/api/transactions",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({

                    type: type.toLowerCase(),

                    amount: Number(amount),

                    category: category,

                    description: description || "",

                    date: date

                })
            }
        );


    const result =
        await response.json();


    alert(result.message);


    loadTransactions();
    loadDashboard();

}

const uploadButton =
    document.querySelector(
        ".secondary-button"
    );

if (uploadButton) {

    uploadButton.addEventListener(
        "click",
        uploadStatement
    );

}


async function uploadStatement() {

    const input =
        document.createElement("input");

    input.type = "file";
    input.accept = ".csv";


    input.click();


    input.addEventListener(
        "change",
        async () => {

            if (!input.files.length)
                return;


            const formData =
                new FormData();

            formData.append(
                "file",
                input.files[0]
            );


            const response =
                await fetch(
                    "/api/upload-statement",
                    {
                        method: "POST",
                        body: formData
                    }
                );


            const result =
                await response.json();


            alert(
                result.message ||
                `${result.imported} transactions imported`
            );


            loadTransactions();
            loadDashboard();

        }
    );

}

const budgetButton =
    document.querySelector(
        "#budget-view .secondary-button"
    );

if (budgetButton) {

    budgetButton.addEventListener(
        "click",
        async () => {

            const category =
                prompt(
                    "Enter budget category:"
                );

            const amount =
                prompt(
                    "Enter monthly budget:"
                );

            if (!category || !amount)
                return;


            const response =
                await fetch(
                    "/api/budgets",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body: JSON.stringify({
                            category: category,
                            amount: Number(amount)
                        })
                    }
                );


            const result =
                await response.json();


            alert(result.message);

        }
    );

}

const goalButton =
    document.querySelector(
        "#budget-view .primary-button"
    );

if (goalButton) {

    goalButton.addEventListener(
        "click",
        async () => {

            const name =
                prompt(
                    "Goal name:"
                );

            const target =
                prompt(
                    "Target amount:"
                );

            if (!name || !target)
                return;


            const response =
                await fetch(
                    "/api/goals",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body: JSON.stringify({

                            name: name,

                            target:
                                Number(target),

                            current: 0,

                            deadline: null

                        })
                    }
                );


            const result =
                await response.json();


            alert(result.message);

        }
    );

}

async function loadSmartCoach() {

    const response =
        await fetch(
            "/api/dashboard"
        );

    const data =
        await response.json();


    const health =
        data.health;


    const healthScore =
        document.querySelector(
            "#coach-view .health-card h3"
        );


    const healthText =
        document.querySelector(
            "#coach-view .health-card p:last-child"
        );


    if (healthScore) {

        healthScore.textContent =
            health.score;

    }


    if (healthText) {

        healthText.textContent =
            health.status;

    }


    const cards =
        document.querySelectorAll(
            "#coach-view .coach-card"
        );


    data.insights.forEach(
        (insight, index) => {

            if (!cards[index])
                return;


            const title =
                cards[index].querySelector("h3");

            const message =
                cards[index].querySelector(
                    "p:last-child"
                );


            if (title)
                title.textContent =
                    insight.title;

            if (message)
                message.textContent =
                    insight.message;

        }
    );

}

loadDashboard();
loadTransactions();
loadSmartCoach();
