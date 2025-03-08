// static/js/dashboard.js

// Dashboard initialization
$(document).ready(function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Poll for updates (if required)
    setupLiveUpdates();
    
    // Initialize any widgets requiring setup
    initializeCharts();
});

// Setup live status updates
function setupLiveUpdates() {
    // Only if we're on the dashboard page and there are active jobs
    if ($('#crawlStatusCard, #aiStatusCard').length && $('.progress-bar').length) {
        // Poll every 5 seconds
        setInterval(updateStatuses, 5000);
    }
}

// Update crawler and AI statuses
function updateStatuses() {
    // Update crawler status
    $.getJSON('/api/stats', function(data) {
        // Update statistics if available
        if (data) {
            updateDashboardStats(data);
        }
    });
}

// Update dashboard statistics
function updateDashboardStats(data) {
    // Only update if elements exist
    if (data.jobs && data.jobs.crawl) {
        $('#queuedCrawlJobs').text(data.jobs.crawl.queued_jobs || 0);
        $('#runningCrawlJobs').text(data.jobs.crawl.running_jobs || 0);
    }
    
    if (data.jobs && data.jobs.ai_processing) {
        $('#queuedAiJobs').text(data.jobs.ai_processing.queued_jobs || 0);
        $('#runningAiJobs').text(data.jobs.ai_processing.running_jobs || 0);
    }
}

// Initialize any charts on the dashboard
function initializeCharts() {
    // Any chart initialization code here
    // (Most charts are initialized inline in the templates)
}

// Utility functions for the dashboard
function formatDuration(seconds) {
    if (!seconds) return '-';
    
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    
    if (hours > 0) {
        return `${hours}h ${minutes % 60}m`;
    } else if (minutes > 0) {
        return `${minutes}m ${Math.floor(seconds % 60)}s`;
    } else {
        return `${Math.floor(seconds)}s`;
    }
}