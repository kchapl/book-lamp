import { JobTracker, type JobStatus, type JobTrackerOptions } from './job-tracker.js';

/**
 * Job Indicator
 * UI component that displays job progress and status updates.
 */
export class JobIndicator extends JobTracker {
    constructor(jobId: string, options: JobTrackerOptions = {}) {
        const uiOnStatusChange = (job: JobStatus) => {
            const progressFill = document.getElementById('job-progress-fill');
            const statusText = document.getElementById('job-status-text');

            if (progressFill) {
                progressFill.style.width = `${job.progress}%`;
            }

            if (statusText) {
                const jobLabels: Record<string, string> = {
                    'import_books': 'Importing books...',
                    'fetch_missing_data': 'Fetching covers & metadata...'
                };
                const label = jobLabels[job.function_name || ''] || `Processing (${job.progress}%)`;
                statusText.textContent = label;
            }

            if (options.onStatusChange) options.onStatusChange(job);
        };

        const uiOnComplete = (job: JobStatus) => {
            console.log(`[JobIndicator] Job completed:`, job);
            if (job.result) {
                const messagesContainer = document.querySelector('.messages');
                if (messagesContainer) {
                    const alert = document.createElement('div');
                    alert.className = 'alert success';
                    alert.innerHTML = `<span>✨</span><span>${job.result}</span>`;
                    messagesContainer.appendChild(alert);

                    // Auto-hide alert after 10 seconds (consistent with base.html logic)
                    setTimeout(() => {
                        alert.style.opacity = '0';
                        alert.style.transform = 'translateY(-10px)';
                        alert.style.transition = 'all 0.5s ease';
                        setTimeout(() => alert.remove(), 500);
                    }, 10000);
                }
            }
            if (options.onComplete) options.onComplete(job);
        };

        const uiOnError = (error: string) => {
            const statusText = document.getElementById('job-status-text');
            if (statusText) {
                statusText.textContent = `Error: ${error}`;
            }
            if (options.onError) options.onError(error);
        };

        super(jobId, {
            ...options,
            onStatusChange: uiOnStatusChange,
            onComplete: uiOnComplete,
            onError: uiOnError
        });
    }

    override start(): void {
        const indicator = document.getElementById('job-indicator');
        if (indicator) {
            indicator.style.display = 'block';
            indicator.style.marginTop = '0px';
        }
        super.start();
    }

    override stop(): void {
        const indicator = document.getElementById('job-indicator');
        if (indicator) {
            setTimeout(() => {
                indicator.style.display = 'none';
            }, 1500);
        }
        super.stop();
    }
}

// Global initialisation logic
document.addEventListener("DOMContentLoaded", () => {
    let activeIndicator: JobIndicator | null = null;

    // 1. Check for job_id in URL (typically after form submission)
    const params = new URLSearchParams(window.location.search);
    const jobIdFromUrl = params.get("job_id");

    if (jobIdFromUrl) {
        console.log(`[JobIndicator] Found job_id in URL: ${jobIdFromUrl}`);
        activeIndicator = new JobIndicator(jobIdFromUrl);
        activeIndicator.start();

        // Clean up the URL by removing the parameter
        const newUrl = window.location.pathname;
        window.history.replaceState({}, document.title, newUrl);
    } else {
        // 2. Check for an active job in storage (persistence across page loads)
        const resumedTracker = JobTracker.resumeActiveJob();
        if (resumedTracker) {
            activeIndicator = new JobIndicator(resumedTracker.jobId, {
                autoRefresh: false
            });
            activeIndicator.start();
        }
    }

    // 3. Check for specific elements with data-job-id attributes
    if (!activeIndicator) {
        const jobElements = document.querySelectorAll<HTMLElement>("[data-job-id]");
        jobElements.forEach((el) => {
            const jobId = el.getAttribute("data-job-id");
            if (jobId) {
                console.log(`[JobIndicator] Found element with data-job-id: ${jobId}`);
                const elementIndicator = new JobIndicator(jobId);
                elementIndicator.start();
                activeIndicator = elementIndicator;
            }
        });
    }

    // Expose to window for manual interaction if needed
    if (activeIndicator) {
        (window as any).currentJobMonitor = activeIndicator;
    }
});
