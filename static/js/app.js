let currentStocks = [];
let autoSaveTimeout = null;
let eventSource = null;
let sseHealthCheckInterval = null;

// SSE connection to receive real-time updates from backend
function connectSSE() {
    // Close existing connection if any
    if (eventSource) {
        eventSource.close();
    }

    // Clear any existing health check interval
    if (sseHealthCheckInterval) {
        clearInterval(sseHealthCheckInterval);
        sseHealthCheckInterval = null;
    }

    eventSource = new EventSource('/api/events');

    eventSource.onopen = () => {
        console.log('SSE connection opened');
    };

    eventSource.addEventListener('connected', (e) => {
        console.log('SSE connected:', JSON.parse(e.data));
        // Fetch latest stocks on reconnection to catch any missed events
        fetchStocks();
    });

    eventSource.addEventListener('stocks-updated', (e) => {
        console.log('SSE: stocks-updated event received', JSON.parse(e.data));
        // Refresh the UI with latest stock data
        fetchStocks();
        // Turn off the blue rectangle indicator (Update task completed)
        document.querySelector('.rect-blue')?.classList.remove('scheduled');
    });

    eventSource.addEventListener('email-updated', (e) => {
        console.log('SSE: email-updated event received', JSON.parse(e.data));
        // Turn off the teal rectangle indicator (Update Email task completed)
        document.querySelector('.rect-teal')?.classList.remove('scheduled');
    });

    eventSource.addEventListener('email-sent', (e) => {
        console.log('SSE: email-sent event received', JSON.parse(e.data));
        // Turn off the orange rectangle indicator (Send Email task completed)
        document.querySelector('.rect-orange')?.classList.remove('scheduled');
    });

    eventSource.onerror = (e) => {
        console.error('SSE connection error:', e);
        eventSource.close();
        // Clear health check on error
        if (sseHealthCheckInterval) {
            clearInterval(sseHealthCheckInterval);
            sseHealthCheckInterval = null;
        }
        // Reconnect after a delay
        setTimeout(() => {
            console.log('Attempting SSE reconnection...');
            connectSSE();
        }, 5000);
    };

    // Health check: verify connection is still alive every 10 seconds
    sseHealthCheckInterval = setInterval(() => {
        if (!eventSource || eventSource.readyState === EventSource.CLOSED) {
            console.log('SSE connection lost (health check), reconnecting...');
            connectSSE();
        }
    }, 10000);
}

// Reconnect SSE when tab becomes visible again
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
        console.log('Tab became visible, checking SSE connection...');
        if (!eventSource || eventSource.readyState !== EventSource.OPEN) {
            console.log('SSE not connected, reconnecting...');
            connectSSE();
        }
    }
});

// Auto-save stocks to backend without fetching prices
async function autoSaveStocks() {
    console.log('Auto-saving stocks...', currentStocks);
    try {
        const response = await fetch('/api/stocks/autosave', {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ stocks: currentStocks })
        });

        if (response.ok) {
            const data = await response.json();
            console.log('Stocks auto-saved successfully:', data);
            // Update local state with response (preserves existing price data)
            if (data.stocks) {
                currentStocks = data.stocks;
            }
        } else {
            console.error('Failed to auto-save stocks');
        }
    } catch (error) {
        console.error('Error auto-saving stocks:', error);
    }
}

// Debounced auto-save (waits 1500ms after last change)
function debouncedAutoSave() {
    if (autoSaveTimeout) {
        clearTimeout(autoSaveTimeout);
    }
    autoSaveTimeout = setTimeout(autoSaveStocks, 1500);
}

function setLoading(isLoading) {
    const overlay = document.getElementById('loading-overlay');
    if (isLoading) {
        overlay.classList.remove('hidden');
    } else {
        overlay.classList.add('hidden');
    }
}

async function fetchStocks() {
    console.log('Fetching stocks...');
    try {
        const response = await fetch('/api/stocks');
        console.log('Response status:', response.status);
        const data = await response.json();
        console.log('Data received:', data);
        if (data.stocks) {
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

    // Handle empty stocks array
    if (stocks.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = `<td colspan="5" class="empty-message">Please hit Add Stock button to add at least 1 stock</td>`;
        tbody.appendChild(row);
        return;
    }

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
            <td class="remove-cell"><button class="remove-btn" data-symbol="${stock.symbol}">&times;</button></td>
            <td><input type="text" class="editable-input symbol-input" data-index="${index}" value="${stock.symbol}"></td>
            <td>$${stock.price.toFixed(2)}</td>
            <td class="${changeClass}">${changeDisplay}</td>
            <td><input type="number" class="editable-input buy-price-input" data-index="${index}" value="${stock.buyPrice.toFixed(2)}" step="0.01"></td>
        `;
        tbody.appendChild(row);
    });

    // Add event listeners to inputs
    // Symbol input change handler - update in memory and auto-save on input
    document.querySelectorAll('.symbol-input').forEach(input => {
        input.addEventListener('input', (e) => {
            const index = parseInt(e.target.dataset.index);
            const newSymbol = e.target.value.toUpperCase().trim();
            e.target.value = newSymbol;
            currentStocks[index].symbol = newSymbol;

            // Reset price data when symbol changes
            currentStocks[index].price = 0;
            currentStocks[index].changePercent = 0;
            currentStocks[index].buyPrice = 0;
            currentStocks[index].diff = 0;

            // Update DOM immediately without re-rendering (to preserve focus)
            const row = e.target.closest('tr');
            const cells = row.querySelectorAll('td');
            cells[2].textContent = '$0.00';  // Price column
            cells[3].textContent = '-';       // Change column
            cells[3].className = '';          // Remove positive/negative class
            const buyPriceInput = cells[4].querySelector('input');
            if (buyPriceInput) {
                buyPriceInput.value = '0.00';
            }

            // Auto-save as user types (debounced)
            debouncedAutoSave();
        });
    });

    document.querySelectorAll('.buy-price-input').forEach(input => {
        input.addEventListener('input', (e) => {
            const index = parseInt(e.target.dataset.index);
            currentStocks[index].buyPrice = parseFloat(e.target.value) || 0;
            // Auto-save as user types (debounced)
            debouncedAutoSave();
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
    setLoading(true);

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

            setLoading(false);
            updateBtn.textContent = 'Saved!';
            setTimeout(() => {
                updateBtn.textContent = 'Update Tracker';
                updateBtn.disabled = false;
            }, 1500);
        } else {
            throw new Error('Failed to save stocks');
        }
    } catch (error) {
        console.error('Error saving stocks:', error);
        setLoading(false);
        updateBtn.textContent = 'Error!';
        setTimeout(() => {
            updateBtn.textContent = 'Update Tracker';
            updateBtn.disabled = false;
        }, 1500);
    }
}

async function updateEmail() {
    const updateEmailBtn = document.getElementById('update-email-btn');
    updateEmailBtn.disabled = true;
    updateEmailBtn.textContent = 'Updating...';
    setLoading(true);

    console.log('Updating email alerts...');

    try {
        const response = await fetch('/api/update-email', {
            method: 'POST'
        });

        if (response.ok) {
            const data = await response.json();
            console.log('Email updated successfully:', data);

            setLoading(false);
            updateEmailBtn.textContent = 'Updated!';
            setTimeout(() => {
                updateEmailBtn.textContent = 'Update Email';
                updateEmailBtn.disabled = false;
            }, 1500);
        } else {
            throw new Error('Failed to update email');
        }
    } catch (error) {
        console.error('Error updating email:', error);
        setLoading(false);
        updateEmailBtn.textContent = 'Error!';
        setTimeout(() => {
            updateEmailBtn.textContent = 'Update Email';
            updateEmailBtn.disabled = false;
        }, 1500);
    }
}

async function sendEmail() {
    const sendEmailBtn = document.getElementById('send-email-btn');
    sendEmailBtn.disabled = true;
    sendEmailBtn.textContent = 'Sending...';
    setLoading(true);

    console.log('Sending test email...');

    try {
        const response = await fetch('/api/send-test-email', {
            method: 'POST'
        });

        if (response.ok) {
            const data = await response.json();
            console.log('Email sent successfully:', data);

            setLoading(false);
            sendEmailBtn.textContent = 'Sent!';
            setTimeout(() => {
                sendEmailBtn.textContent = 'Send Email';
                sendEmailBtn.disabled = false;
            }, 1500);
        } else {
            throw new Error('Failed to send email');
        }
    } catch (error) {
        console.error('Error sending email:', error);
        setLoading(false);
        sendEmailBtn.textContent = 'Error!';
        setTimeout(() => {
            sendEmailBtn.textContent = 'Send Email';
            sendEmailBtn.disabled = false;
        }, 1500);
    }
}

async function checkScheduleStatus() {
    try {
        const response = await fetch('/api/schedule-status');
        const data = await response.json();

        const rectBlue = document.querySelector('.rect-blue');
        const rectTeal = document.querySelector('.rect-teal');
        const rectOrange = document.querySelector('.rect-orange');

        // Update each rectangle part based on its task status
        if (data.update) {
            rectBlue.classList.add('scheduled');
        } else {
            rectBlue.classList.remove('scheduled');
        }

        if (data.updateEmail) {
            rectTeal.classList.add('scheduled');
        } else {
            rectTeal.classList.remove('scheduled');
        }

        if (data.sendEmail) {
            rectOrange.classList.add('scheduled');
        } else {
            rectOrange.classList.remove('scheduled');
        }
    } catch (error) {
        console.error('Error checking schedule status:', error);
    }
}

async function updateSchedule() {
    const scheduleBtn = document.getElementById('schedule-btn');
    const triggerTimeInput = document.getElementById('trigger-time-input');
    const triggerTime = triggerTimeInput.value.trim();

    if (!triggerTime) {
        alert('Please enter a trigger time (e.g., 2026-01-23T07:00:00+08:00)');
        return;
    }

    scheduleBtn.disabled = true;
    scheduleBtn.textContent = 'Scheduling...';

    console.log('Updating schedule with trigger time:', triggerTime);

    try {
        const response = await fetch('/api/schedule', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ trigger_time: triggerTime })
        });

        const data = await response.json();

        if (data.success) {
            console.log('Schedule updated successfully:', data);
            // Add scheduled class to all rectangle parts
            document.querySelector('.rect-blue').classList.add('scheduled');
            document.querySelector('.rect-teal').classList.add('scheduled');
            document.querySelector('.rect-orange').classList.add('scheduled');
            scheduleBtn.textContent = 'Scheduled!';
            setTimeout(() => {
                scheduleBtn.textContent = 'Schedule';
                scheduleBtn.disabled = false;
            }, 1500);
        } else {
            throw new Error(data.error || 'Failed to update schedule');
        }
    } catch (error) {
        console.error('Error updating schedule:', error);
        scheduleBtn.textContent = 'Error!';
        setTimeout(() => {
            scheduleBtn.textContent = 'Schedule';
            scheduleBtn.disabled = false;
        }, 1500);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    fetchStocks();
    connectSSE();  // Establish SSE connection for real-time updates
    checkScheduleStatus();  // Check if tasks are scheduled and update rectangle indicator
    document.getElementById('add-btn').addEventListener('click', addStock);
    document.getElementById('update-btn').addEventListener('click', saveStocks);
    document.getElementById('update-email-btn').addEventListener('click', updateEmail);
    document.getElementById('send-email-btn').addEventListener('click', sendEmail);
    document.getElementById('schedule-btn').addEventListener('click', updateSchedule);
});
