// static/js/ai.js

$(document).ready(function() {
    // Load model button
    $('#loadModelBtn').click(function() {
        if (!confirm('Are you sure you want to load the AI model? This may take some time.')) {
            return;
        }
        
        // Show loading state
        $(this).prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Loading...');
        
        // Make API call
        $.post('/ai/load_model', function(data) {
            if (data.status === 'success') {
                window.location.reload();
            } else {
                alert(`Error: ${data.message}`);
                // Reset button
                $('#loadModelBtn').prop('disabled', false).text('Load Model');
            }
        }).fail(function() {
            alert('Failed to load model. Please try again.');
            // Reset button
            $('#loadModelBtn').prop('disabled', false).text('Load Model');
        });
    });
    
    // Unload model button
    $('#unloadModelBtn').click(function() {
        if (!confirm('Are you sure you want to unload the AI model? This will interrupt any ongoing processing.')) {
            return;
        }
        
        // Show loading state
        $(this).prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Unloading...');
        
        // Make API call
        $.post('/ai/unload_model', function(data) {
            if (data.status === 'success') {
                window.location.reload();
            } else {
                alert(`Error: ${data.message}`);
                // Reset button
                $('#unloadModelBtn').prop('disabled', false).text('Unload Model');
            }
        }).fail(function() {
            alert('Failed to unload model. Please try again.');
            // Reset button
            $('#unloadModelBtn').prop('disabled', false).text('Unload Model');
        });
    });
    
    // Poll for AI job status updates
    function pollAiJobStatus() {
        // Implementation would be similar to crawling.js
        // Would poll an endpoint that returns AI job status
    }
    
    // Initialize AI job filters
    $('.ai-job-filter').change(function() {
        $(this).closest('form').submit();
    });
});