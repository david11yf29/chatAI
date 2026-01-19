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

async function removeStock(symbol) {
    console.log('Removing stock:', symbol);
    try {
        const response = await fetch(`/api/stocks/${encodeURIComponent(symbol)}`, {
            method: 'DELETE'
        });
        const data = await response.json();
        console.log('Remove response:', data);
        if (data.success) {
            await fetchStocks();
        }
    } catch (error) {
        console.error('Error removing stock:', error);
    }
}

function addStock() {
    const newStock = {
        symbol: "",
        name: "New Stock",
        price: 0,
        changePercent: 0,
        date: "",
        buyPrice: 0,
        diff: 0
    };
    currentStocks.push(newStock);
    renderStocks(currentStocks);

    // Focus the new symbol input for immediate editing
    const symbolInputs = document.querySelectorAll('.symbol-input');
    const lastInput = symbolInputs[symbolInputs.length - 1];
    if (lastInput) {
        lastInput.focus();
    }
}

function renderStocks(stocks) {
    const tbody = document.getElementById('stock-body');
    tbody.innerHTML = '';

    stocks.forEach((stock, index) => {
        const row = document.createElement('tr');

        // Format change percentage with sign and color
        let changeDisplay = '-';
        let changeClass = '';
        if (stock.changePercent !== null && stock.changePercent !== undefined) {
            const sign = stock.changePercent >= 0 ? '+' : '';
            changeDisplay = `${sign}${stock.changePercent.toFixed(2)}%`;
            changeClass = stock.changePercent >= 0 ? 'positive-change' : 'negative-change';
        }

        row.innerHTML = `
            <td class="remove-cell"><button class="remove-btn" data-symbol="${stock.symbol}">Remove</button></td>
            <td><input type="text" class="editable-input symbol-input" data-index="${index}" value="${stock.symbol}"></td>
            <td>$${stock.price.toFixed(2)}</td>
            <td class="${changeClass}">${changeDisplay}</td>
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

    // Remove button click handler
    document.querySelectorAll('.remove-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const symbol = e.target.dataset.symbol;
            const index = parseInt(e.target.closest('tr').querySelector('.symbol-input').dataset.index);

            // If symbol is empty (unsaved new row), just remove from local array
            if (!symbol || symbol.trim() === '') {
                currentStocks.splice(index, 1);
                renderStocks(currentStocks);
            } else {
                removeStock(symbol);
            }
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
    document.getElementById('add-btn').addEventListener('click', addStock);
    document.getElementById('update-btn').addEventListener('click', saveStocks);
});
