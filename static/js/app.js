let currentStocks = [];
let originalSymbols = [];

async function fetchStocks() {
    console.log('Fetching stocks...');
    try {
        const response = await fetch('/api/stocks');
        console.log('Response status:', response.status);
        const data = await response.json();
        console.log('Data received:', data);
        if (data.stocks && data.stocks.length > 0) {
            currentStocks = data.stocks;
            originalSymbols = data.stocks.map(s => s.symbol);
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
    document.querySelectorAll('.symbol-input').forEach(input => {
        input.addEventListener('change', async (e) => {
            const index = parseInt(e.target.dataset.index);
            const newSymbol = e.target.value.toUpperCase().trim();
            e.target.value = newSymbol;

            if (newSymbol && newSymbol !== currentStocks[index].symbol) {
                currentStocks[index].symbol = newSymbol;
                // Fetch company name from API
                await fetchAndUpdateCompanyName(index, newSymbol);
            }
        });
    });

    document.querySelectorAll('.buy-price-input').forEach(input => {
        input.addEventListener('change', (e) => {
            const index = parseInt(e.target.dataset.index);
            currentStocks[index].buyPrice = parseFloat(e.target.value) || 0;
        });
    });
}

async function fetchAndUpdateCompanyName(index, symbol) {
    console.log(`Fetching company name for ${symbol}...`);
    try {
        const response = await fetch(`/api/stock-info/${symbol}`);
        const data = await response.json();
        console.log('Stock info received:', data);

        if (data.name && !data.error) {
            currentStocks[index].name = data.name;
            console.log(`Updated name for ${symbol}: ${data.name}`);
        } else {
            console.warn(`Could not find company name for ${symbol}`);
        }
    } catch (error) {
        console.error(`Error fetching stock info for ${symbol}:`, error);
    }
}

async function saveStocks() {
    const updateBtn = document.getElementById('update-btn');
    updateBtn.disabled = true;

    // First, check if any symbols have changed and fetch their company names
    const symbolsToLookup = [];
    for (let i = 0; i < currentStocks.length; i++) {
        const currentSymbol = currentStocks[i].symbol.toUpperCase().trim();
        if (currentSymbol !== originalSymbols[i]) {
            symbolsToLookup.push({ index: i, symbol: currentSymbol });
        }
    }

    if (symbolsToLookup.length > 0) {
        updateBtn.textContent = 'Looking up...';
        console.log('Fetching company names for changed symbols:', symbolsToLookup);

        // Fetch all company names in parallel
        await Promise.all(symbolsToLookup.map(async ({ index, symbol }) => {
            await fetchAndUpdateCompanyName(index, symbol);
        }));
    }

    console.log('Saving stocks...', currentStocks);
    updateBtn.textContent = 'Saving...';

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
            // Update originalSymbols to reflect the saved state
            originalSymbols = currentStocks.map(s => s.symbol);
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
