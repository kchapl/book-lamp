/**
 * Job Tracker
 * Core logic for polling background job status and persistence.
 */

export interface JobStatus {
    id: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    progress: number;
    result?: string;
    error?: string;
    function_name?: string;
}

export interface JobTrackerOptions {
    checkInterval?: number;
    autoRefresh?: boolean;
    onStatusChange?: (job: JobStatus) => void;
    onComplete?: (job: JobStatus) => void;
    onError?: (error: string) => void;
}

export class JobTracker {
    static readonly STORAGE_KEY = "book_lamp_active_job_id";

    private intervalId: number | null = null;
    public readonly jobId: string;
    private readonly checkInterval: number;
    private readonly autoRefresh: boolean;
    private readonly onStatusChange: (job: JobStatus) => void;
    private readonly onComplete: (job: JobStatus) => void;
    private readonly onError: (error: string) => void;

    constructor(jobId: string, options: JobTrackerOptions = {}) {
        this.jobId = jobId;
        this.checkInterval = options.checkInterval || 2000;
        this.autoRefresh = options.autoRefresh !== false;
        this.onStatusChange = options.onStatusChange || (() => { });
        this.onComplete = options.onComplete || (() => { });
        this.onError = options.onError || (() => { });
    }

    /**
     * Starts monitoring the job.
     */
    start(): void {
        console.log(`[JobTracker] Starting tracker for job ${this.jobId}`);
        localStorage.setItem(JobTracker.STORAGE_KEY, this.jobId);

        this.check();
        this.intervalId = window.setInterval(() => this.check(), this.checkInterval);
    }

    /**
     * Stops monitoring the job.
     */
    stop(): void {
        console.log(`[JobTracker] Stopping tracker for job ${this.jobId}`);
        if (this.intervalId !== null) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
        localStorage.removeItem(JobTracker.STORAGE_KEY);
    }

    /**
     * Performs a status check.
     */
    private async check(): Promise<void> {
        try {
            const response = await fetch(`/api/jobs/${this.jobId}`);
            if (!response.ok) {
                if (response.status === 404) {
                    this.onError("Job not found");
                    this.stop();
                    return;
                }
                throw new Error(`HTTP status ${response.status}`);
            }

            const job: JobStatus = await response.json();
            console.log(`[JobTracker] Job ${this.jobId} status: ${job.status}`);

            this.onStatusChange(job);

            if (job.status === "completed") {
                console.log(`[JobTracker] Job ${this.jobId} completed`);
                this.stop();
                this.onComplete(job);

                if (this.autoRefresh) {
                    console.log(`[JobTracker] Auto-refreshing page in 2 seconds...`);
                    setTimeout(() => location.reload(), 2000);
                }
            } else if (job.status === "failed") {
                console.error(`[JobTracker] Job ${this.jobId} failed:`, job.error);
                this.stop();
                this.onError(job.error || "Job failed");
            }
        } catch (error) {
            console.error(`[JobTracker] Error checking job status:`, error);
        }
    }

    /**
     * Resumes monitoring of a job found in localStorage.
     */
    static resumeActiveJob(): JobTracker | null {
        const jobId = localStorage.getItem(JobTracker.STORAGE_KEY);
        if (jobId) {
            console.log(`[JobTracker] Found active job in localStorage: ${jobId}`);
            // Return a tracker instance (autoRefresh disabled by default for resumed jobs)
            return new JobTracker(jobId, { autoRefresh: false });
        }
        return null;
    }
}
