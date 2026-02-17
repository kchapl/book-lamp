// Enhanced JobMonitor that adds UI feedback to the base JobMonitor
// Requires job-monitor.js to be loaded first

class EnhancedJobMonitor extends JobMonitor {
    constructor(jobId, options = {}) {
        // Define UI update callbacks
        const onStatusChange = (job) => {
            const progressFill = document.getElementById('job-progress-fill');
            const statusText = document.getElementById('job-status-text');

            if (progressFill) {
                progressFill.style.width = job.progress + '%';
            }

            // Update status text based on function name
            if (statusText) {
                const jobLabels = {
                    'import_books': 'Importing books...',
                    'fetch_missing_data': 'Fetching covers & metadata...'
                };
                const label = jobLabels[job.function_name] || `Processing (${job.progress}%)`;
                statusText.textContent = label;
            }
        };

        const onComplete = (job) => {
            console.log(`[EnhancedJobMonitor] Job completed:`, job);
            if (job.result) {
                const messagesContainer = document.querySelector('.messages');
                if (messagesContainer) {
                    const alert = document.createElement('div');
                    alert.className = 'alert success';
                    alert.innerHTML = `<span>✨</span><span>${job.result}</span>`;
                    messagesContainer.appendChild(alert);

                    // Auto-hide after 10 seconds (matching base.html logic)
                    setTimeout(function () {
                        alert.style.opacity = '0';
                        alert.style.transform = 'translateY(-10px)';
                        alert.style.transition = 'all 0.5s ease';
                        setTimeout(function () {
                            alert.remove();
                        }, 500);
                    }, 10000);
                }
            }
        };

        const onError = (error) => {
            const statusText = document.getElementById('job-status-text');
            if (statusText) {
                statusText.textContent = `Error: ${error}`;
            }
        };

        // Pass callbacks to parent constructor
        super(jobId, {
            ...options,
            onStatusChange: onStatusChange,
            onComplete: onComplete,
            onError: onError
        });
    }

    start() {
        const indicator = document.getElementById('job-indicator');
        if (indicator) {
            indicator.style.display = 'block';
            indicator.style.marginTop = '0px';
        }

        super.start();
    }

    stop() {
        const indicator = document.getElementById('job-indicator');
        if (indicator) {
            setTimeout(() => {
                indicator.style.display = 'none';
            }, 1500);
        }
        super.stop();
    }
}

// Check for new or active jobs on page load
document.addEventListener("DOMContentLoaded", function () {
    let monitor = null;

    // First, check for a job_id in the URL (from form submission)
    const params = new URLSearchParams(window.location.search);
    const jobIdFromUrl = params.get("job_id");

    if (jobIdFromUrl) {
        console.log(`[JobMonitor] Found job_id in URL: ${jobIdFromUrl}`);
        monitor = new EnhancedJobMonitor(jobIdFromUrl);
        monitor.start();

        // Clean up URL by removing job_id parameter
        const newUrl = window.location.pathname;
        window.history.replaceState({}, document.title, newUrl);
    } else {
        // Check if there's an active job in localStorage from a previous page
        const resumedBaseMonitor = JobMonitor.resumeActiveJob();
        if (resumedBaseMonitor) {
            // Create an EnhancedJobMonitor instance with the same job ID
            monitor = new EnhancedJobMonitor(resumedBaseMonitor.jobId, {
                autoRefresh: false
            });
            monitor.start();
        }
    }

    // Store globally for manual interaction if needed
    if (monitor) {
        window.currentJobMonitor = monitor;
    }

    // Also check for data-job-id attribute on elements
    const jobElements = document.querySelectorAll("[data-job-id]");
    if (jobElements.length > 0 && !monitor) {
        jobElements.forEach((el) => {
            const jobId = el.getAttribute("data-job-id");
            console.log(`[JobMonitor] Found data-job-id: ${jobId}`);
            const elementMonitor = new EnhancedJobMonitor(jobId);
            elementMonitor.start();
            window.currentJobMonitor = elementMonitor;
        });
    }
});
