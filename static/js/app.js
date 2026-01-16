async function fetchStocks() {
    console.log('Fetching stocks...');
    try {
        const response = await fetch('/api/stocks');
        console.log('Response status:', response.status);
        const data = await response.json();
        console.log('Data received:', data);
        if (data.stocks && data.stocks.length > 0) {
            renderStocks(data.stocks);
        } else {
            console.error('No stocks in response');
        }
    } catch (error) {
        console.error('Error fetching stocks:', error);
    }
}

function renderStocks(stocks) {
    const tbody = document.getElementById('stock-body');
    tbody.innerHTML = '';

    stocks.forEach(stock => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${stock.symbol}</td>
            <td>$${stock.price.toFixed(2)}</td>
        `;
        tbody.appendChild(row);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    fetchStocks();
    document.getElementById('update-btn').addEventListener('click', fetchStocks);
});
