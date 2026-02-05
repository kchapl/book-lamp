/**
 * Job Status Monitoring
 * Simple utility to check background job status and auto-refresh when complete
 * Persists job tracking in localStorage across page navigation
 */

class JobMonitor {
  static STORAGE_KEY = "book_lamp_active_job_id";

  constructor(jobId, options = {}) {
    this.jobId = jobId;
    this.checkInterval = options.checkInterval || 2000; // ms between checks
    this.autoRefresh = options.autoRefresh !== false; // default true
    this.onStatusChange = options.onStatusChange || (() => {});
    this.onComplete = options.onComplete || (() => {});
    this.onError = options.onError || (() => {});
    this.intervalId = null;
  }

  start() {
    console.log(`[JobMonitor] Starting to monitor job ${this.jobId}`);
    // Store job ID in localStorage so it persists across page navigation
    localStorage.setItem(JobMonitor.STORAGE_KEY, this.jobId);
    
    this.check(); // Check immediately
    this.intervalId = setInterval(() => this.check(), this.checkInterval);
  }

  stop() {
    console.log(`[JobMonitor] Stopping monitor for job ${this.jobId}`);
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
    // Clear from localStorage
    localStorage.removeItem(JobMonitor.STORAGE_KEY);
  }

  async check() {
    try {
      const response = await fetch(`/api/jobs/${this.jobId}`);
      if (!response.ok) {
        if (response.status === 404) {
          this.onError("Job not found");
          this.stop();
          return;
        }
        throw new Error(`HTTP ${response.status}`);
      }

      const job = await response.json();
      console.log(`[JobMonitor] Job ${this.jobId} status:`, job.status);

      this.onStatusChange(job);

      if (job.status === "completed") {
        console.log(`[JobMonitor] Job ${this.jobId} completed!`);
        this.stop();
        this.onComplete(job);

        if (this.autoRefresh) {
          console.log(`[JobMonitor] Auto-refreshing page in 2 seconds...`);
          setTimeout(() => location.reload(), 2000);
        }
      } else if (job.status === "failed") {
        console.error(`[JobMonitor] Job ${this.jobId} failed:`, job.error);
        this.stop();
        this.onError(job.error || "Job failed");
      }
    } catch (error) {
      console.error(`[JobMonitor] Error checking job status:`, error);
    }
  }

  /**
   * Check if there's an active job in localStorage and resume monitoring
   * Returns a Job Monitor instance (or null if no active job)
   * Note: Does NOT call start() - caller should do that
   */
  static resumeActiveJob() {
    const jobId = localStorage.getItem(JobMonitor.STORAGE_KEY);
    if (jobId) {
      console.log(`[JobMonitor] Found active job in localStorage: ${jobId}`);
      const monitor = new JobMonitor(jobId, {
        autoRefresh: false // Don't auto-refresh when resuming, let user control navigation
      });
      return monitor;
    }
    return null;
  }
}

