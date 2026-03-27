/**
 * dashboard.js
 * Updates Analytics charts from localStorage / API
 */

let trendChart, balanceChart;

function initCharts() {
    const trendCtx = document.getElementById('trendChart')?.getContext('2d');
    const balanceCtx = document.getElementById('balanceChart')?.getContext('2d');
    if (!trendCtx || !balanceCtx) return;

    if (trendChart) trendChart.destroy();
    if (balanceChart) balanceChart.destroy();

    trendChart = new Chart(trendCtx, {
        type: 'line',
        data: { labels: [], datasets: [{
            label: 'Score',
            data: [],
            borderColor: '#2A7DE1',
            fill: true,
            backgroundColor: 'rgba(42, 125, 225, 0.1)',
            tension: 0.4
        }]},
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { y: { min: 0, max: 100 } }
        }
    });

    balanceChart = new Chart(balanceCtx, {
        type: 'doughnut',
        data: {
            labels: ['Good (s)', 'Bad (s)'],
            datasets: [{
                data: [0, 0],
                backgroundColor: ['#22C55E', '#EF4444']
            }]
        },
        options: { responsive: true, maintainAspectRatio: false }
    });
}

async function loadDashboardData() {
    let sessions = [];
    let source = 'local';

    try {
        const resp = await fetch('/api/sessions');
        const data = await resp.json();
        sessions = data.sessions || [];
        source = data.source || 'local';
        console.log(`[Dashboard] Loaded ${sessions.length} sessions from ${source}`);
    } catch (err) {
        console.warn("[Dashboard] Failed to fetch from API, falling back to localStorage", err);
        sessions = JSON.parse(localStorage.getItem('spine_sessions') || '[]');
    }

    if (sessions.length === 0) {
        document.getElementById('anTotSessions').textContent = '0';
        return;
    }

    const n = sessions.length;
    document.getElementById('anTotSessions').textContent = n;

    const avgScore = sessions.reduce((a, b) => a + b.posture_score, 0) / n;
    document.getElementById('anAvgScore').textContent = `${Math.round(avgScore)}%`;

    const totalGood = sessions.reduce((a, b) => a + b.good_posture_time, 0);
    const anGood = document.getElementById('anGoodTime');
    if (anGood) anGood.textContent = `${Math.round(totalGood)}s`;

    // Update Balance Chart
    if (balanceChart) {
        const totalBad = sessions.reduce((a, b) => a + b.bad_posture_time, 0);
        balanceChart.data.datasets[0].data = [totalGood, totalBad];
        balanceChart.update();
    }

    // Update Trend Chart
    if (trendChart) {
        const recent = sessions.slice(-20);
        trendChart.data.labels = recent.map(s => s.time);
        trendChart.data.datasets[0].data = recent.map(s => s.posture_score);
        trendChart.update();
    }

    // Update Table
    const tbody = document.getElementById('analyticsTbody');
    if (tbody) {
        tbody.innerHTML = sessions.reverse().map(s => `
            <tr>
                <td>${s.date} ${s.time}</td>
                <td>${s.posture_score}%</td>
                <td>${s.good_posture_time}s</td>
                <td>${s.bad_posture_time}s</td>
                <td>${s.bad_streak_count}</td>
            </tr>
        `).join('');
    }
}

// Hook for live updates from posture.js
window.updateLiveGraph = (history) => {
    if (!trendChart) initCharts();
    trendChart.data.labels = history.map(h => h.time);
    trendChart.data.datasets[0].data = history.map(h => h.score);
    trendChart.update('none'); // silent update
};

window.loadDashboardData = loadDashboardData;

document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    loadDashboardData();
});
