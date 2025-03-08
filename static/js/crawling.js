// static/js/crawling.js

$(document).ready(function() {
    // Poll for crawl job status updates
    function pollJobStatus() {
        const jobId = $('#jobStatusCard').data('job-id');
        
        if (!jobId || $('#jobStatusCard').data('status') !== 'running') {
            return;
        }
        
        $.getJSON(`/crawl_status/${jobId}`, function(data) {
            if (data && data.status) {
                // Update status display
                updateJobStatus(data);
                
                // Continue polling if job is still running
                if (data.status === 'running') {
                    setTimeout(pollJobStatus, 5000);
                } else {
                    // Reload page if job completed or failed
                    window.location.reload();
                }
            }
        });
    }
    
    // Update job status UI
    function updateJobStatus(data) {
        if (data.progress) {
            // Update progress bar
            $('.progress-bar')
                .css('width', `${data.progress.progress_percentage}%`)
                .attr('aria-valuenow', data.progress.progress_percentage)
                .text(`${data.progress.progress_percentage}%`);
            
            // Update pages count
            $('#pagesCrawled').text(data.progress.pages_crawled || 0);
            
            // Update current URL if available
            if (data.progress.current_url) {
                $('#currentUrl').text(data.progress.current_url);
            }
            
            // Update content category counts
            $('#admissionPages').text(data.progress.admission_pages || 0);
            $('#placementPages').text(data.progress.placement_pages || 0);
            $('#internshipPages').text(data.progress.internship_pages || 0);
            $('#otherPages').text(data.progress.other_pages || 0);
        }
    }
    
    // Start polling if on job details page with a running job
    if ($('#jobStatusCard').length && $('#jobStatusCard').data('status') === 'running') {
        pollJobStatus();
    }
    
    // Initialize crawl job filter
    $('#statusFilter').change(function() {
        $(this).closest('form').submit();
    });
});
