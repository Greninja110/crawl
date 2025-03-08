// static/js/colleges.js

$(document).ready(function() {
    // College search functionality
    $('#collegeSearch').on('input', function() {
        const searchTerm = $(this).val().toLowerCase();
        
        $('.college-row').each(function() {
            const collegeName = $(this).find('.college-name').text().toLowerCase();
            const collegeType = $(this).find('.college-type').text().toLowerCase();
            const collegeState = $(this).find('.college-state').text().toLowerCase();
            
            if (collegeName.includes(searchTerm) || 
                collegeType.includes(searchTerm) || 
                collegeState.includes(searchTerm)) {
                $(this).show();
            } else {
                $(this).hide();
            }
        });
    });
    
    // College filter functionality
    $('.college-filter').change(function() {
        $('#collegeFilterForm').submit();
    });
    
    // Start crawl handlers
    $('.start-crawl-btn').click(function() {
        const collegeId = $(this).data('college-id');
        const collegeName = $(this).data('college-name');
        
        if (confirm(`Are you sure you want to start crawling ${collegeName}?`)) {
            // Show loading state
            $(this).prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span>');
            
            // Make API call
            $.post(`/start_crawl/${collegeId}`, function(data) {
                if (data.status === 'success') {
                    // Redirect to job details page
                    window.location.href = `/crawl_jobs/${data.job_id}`;
                } else {
                    alert(`Error: ${data.message}`);
                    // Reset button
                    $('.start-crawl-btn').prop('disabled', false).html('<i class="bi bi-robot"></i>');
                }
            }).fail(function() {
                alert('Failed to start crawl. Please try again.');
                // Reset button
                $('.start-crawl-btn').prop('disabled', false).html('<i class="bi bi-robot"></i>');
            });
        }
    });
    
    // Form validation for college add/edit
    $('#collegeForm').submit(function(e) {
        // Validate URL format
        const websiteInput = $('#website');
        const websiteValue = websiteInput.val();
        
        if (websiteValue && !isValidUrl(websiteValue)) {
            e.preventDefault();
            alert('Please enter a valid URL including http:// or https://');
            websiteInput.focus();
            return false;
        }
        
        return true;
    });
    
    // Helper function to validate URL
    function isValidUrl(url) {
        try {
            new URL(url);
            return true;
        } catch (e) {
            return false;
        }
    }
});