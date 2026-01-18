let currentStocks = [];

async function fetchStocks() {
    console.log('Fetching stocks...');
    try {
        const response = await fetch('/api/stocks');
        console.log('Response status:', response.status);
        const data = await response.json();
        console.log('Data received:', data);
        if (data.stocks && data.stocks.length > 0) {
            currentStocks = data.stocks;
            renderStocks(currentStocks);
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

    stocks.forEach((stock, index) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td><input type="text" class="editable-input symbol-input" data-index="${index}" value="${stock.symbol}"></td>
            <td>$${stock.price.toFixed(2)}</td>
            <td><input type="number" class="editable-input buy-price-input" data-index="${index}" value="${stock.buyPrice.toFixed(2)}" step="0.01"></td>
        `;
        tbody.appendChild(row);
    });

    // Add event listeners to inputs
    // Symbol input change handler - just store in memory (no API call)
    // Name and price will be fetched when "Update" is clicked
    document.querySelectorAll('.symbol-input').forEach(input => {
        input.addEventListener('input', (e) => {
            const index = parseInt(e.target.dataset.index);
            const newSymbol = e.target.value.toUpperCase().trim();
            e.target.value = newSymbol;
            currentStocks[index].symbol = newSymbol;
        });
    });

    document.querySelectorAll('.buy-price-input').forEach(input => {
        input.addEventListener('input', (e) => {
            const index = parseInt(e.target.dataset.index);
            currentStocks[index].buyPrice = parseFloat(e.target.value) || 0;
        });
    });
}

async function saveStocks() {
    const updateBtn = document.getElementById('update-btn');
    updateBtn.disabled = true;
    updateBtn.textContent = 'Saving...';

    console.log('Saving stocks...', currentStocks);

    try {
        const response = await fetch('/api/stocks', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ stocks: currentStocks })
        });

        if (response.ok) {
            const data = await response.json();
            console.log('Stocks saved successfully:', data);

            // Re-fetch from source of truth to get updated prices
            await fetchStocks();

            updateBtn.textContent = 'Saved!';
            setTimeout(() => {
                updateBtn.textContent = 'Update';
                updateBtn.disabled = false;
            }, 1500);
        } else {
            throw new Error('Failed to save stocks');
        }
    } catch (error) {
        console.error('Error saving stocks:', error);
        updateBtn.textContent = 'Error!';
        setTimeout(() => {
            updateBtn.textContent = 'Update';
            updateBtn.disabled = false;
        }, 1500);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    fetchStocks();
    document.getElementById('update-btn').addEventListener('click', saveStocks);
});
