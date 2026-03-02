document.addEventListener('DOMContentLoaded', function() {
    const ctx = document.getElementById('healthChart');
    if (!ctx) return; //exit if canvas doesn't exist

    const data = window.chartData;

    //check if we actually have data to plot
    if (data.labels.length > 0) {
        new Chart(ctx.getContext('2d'), {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [
                    { label: 'Systolic', data: data.systolic, borderColor: 'red' },
                    { label: 'Diastolic', data: data.diastolic, borderColor: 'blue' },
                    { label: 'Pulse', data: data.pulse, borderColor: 'green' }
                ]
            },
            options: { responsive: true }
        });
    }
});