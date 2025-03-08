// static/js/form-validation.js

/**
 * Form validation utilities for College Data Crawler
 */

// Form validation object
const FormValidator = {
    // Initialize validation for a form
    init: function(formId, options = {}) {
        const form = document.getElementById(formId);
        if (!form) return false;
        
        // Default options
        const defaults = {
            validateOnSubmit: true,
            validateOnChange: true,
            validateOnBlur: true,
            showValidFeedback: false,
            errorClass: 'is-invalid',
            validClass: 'is-valid',
            errorFeedbackClass: 'invalid-feedback',
            validFeedbackClass: 'valid-feedback'
        };
        
        // Merge options
        const settings = {...defaults, ...options};
        
        // Store settings
        form.validationSettings = settings;
        
        // Add form submission handler
        if (settings.validateOnSubmit) {
            form.addEventListener('submit', function(e) {
                if (!FormValidator.validateForm(formId)) {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    // Focus the first invalid field
                    const firstInvalid = form.querySelector('.' + settings.errorClass);
                    if (firstInvalid) {
                        firstInvalid.focus();
                    }
                }
            });
        }
        
        // Add input change/blur handlers
        if (settings.validateOnChange || settings.validateOnBlur) {
            const inputs = form.querySelectorAll('input, select, textarea');
            
            inputs.forEach(input => {
                if (settings.validateOnChange) {
                    input.addEventListener('input', function() {
                        FormValidator.validateField(this);
                    });
                    
                    input.addEventListener('change', function() {
                        FormValidator.validateField(this);
                    });
                }
                
                if (settings.validateOnBlur) {
                    input.addEventListener('blur', function() {
                        FormValidator.validateField(this);
                    });
                }
            });
        }
        
        return true;
    },
    
    // Validate an entire form
    validateForm: function(formId) {
        const form = document.getElementById(formId);
        if (!form) return false;
        
        let isValid = true;
        const inputs = form.querySelectorAll('input, select, textarea');
        
        inputs.forEach(input => {
            if (!FormValidator.validateField(input)) {
                isValid = false;
            }
        });
        
        return isValid;
    },
    
    // Validate a single field
    validateField: function(field) {
        // If field is a string (id), get the element
        if (typeof field === 'string') {
            field = document.getElementById(field);
        }
        
        if (!field) return false;
        
        // Get the form's validation settings
        const form = field.form;
        if (!form || !form.validationSettings) return false;
        
        const settings = form.validationSettings;
        
        // Reset validation state
        field.classList.remove(settings.errorClass, settings.validClass);
        
        // Remove existing feedback elements
        const parent = field.parentNode;
        const existingFeedback = parent.querySelectorAll('.' + settings.errorFeedbackClass + ', .' + settings.validFeedbackClass);
        existingFeedback.forEach(el => el.remove());
        
        // Skip disabled or hidden fields
        if (field.disabled || field.type === 'hidden') {
            return true;
        }
        
        // Check HTML5 validity
        let isValid = field.checkValidity();
        
        // Additional validation based on data attributes
        if (isValid) {
            // Validate URL format
            if (field.dataset.validateUrl !== undefined && field.value.trim() !== '') {
                isValid = FormValidator.isValidUrl(field.value);
            }
            
            // Validate email format
            if (field.dataset.validateEmail !== undefined && field.value.trim() !== '') {
                isValid = FormValidator.isValidEmail(field.value);
            }
            
            // Validate password strength
            if (field.dataset.validatePassword !== undefined && field.value.trim() !== '') {
                isValid = FormValidator.isValidPassword(field.value);
            }
            
            // Validate password match
            if (field.dataset.validateMatch) {
                const matchField = document.getElementById(field.dataset.validateMatch);
                if (matchField) {
                    isValid = field.value === matchField.value;
                }
            }
            
            // Validate minimum length
            if (field.dataset.validateMinLength && field.value.trim() !== '') {
                isValid = field.value.length >= parseInt(field.dataset.validateMinLength, 10);
            }
            
            // Validate maximum length
            if (field.dataset.validateMaxLength && field.value.trim() !== '') {
                isValid = field.value.length <= parseInt(field.dataset.validateMaxLength, 10);
            }
            
            // Validate numeric value
            if (field.dataset.validateNumeric !== undefined && field.value.trim() !== '') {
                isValid = FormValidator.isNumeric(field.value);
            }
            
            // Validate integer value
            if (field.dataset.validateInteger !== undefined && field.value.trim() !== '') {
                isValid = FormValidator.isInteger(field.value);
            }
            
            // Validate minimum value
            if (field.dataset.validateMin && field.value.trim() !== '') {
                isValid = parseFloat(field.value) >= parseFloat(field.dataset.validateMin);
            }
            
            // Validate maximum value
            if (field.dataset.validateMax && field.value.trim() !== '') {
                isValid = parseFloat(field.value) <= parseFloat(field.dataset.validateMax);
            }
        }
        
        // Update field state
        if (isValid) {
            if (settings.showValidFeedback) {
                field.classList.add(settings.validClass);
                
                // Add valid feedback message if provided
                if (field.dataset.validFeedback) {
                    const feedback = document.createElement('div');
                    feedback.className = settings.validFeedbackClass;
                    feedback.textContent = field.dataset.validFeedback;
                    parent.appendChild(feedback);
                }
            }
        } else {
            field.classList.add(settings.errorClass);
            
            // Add error feedback message
            const feedback = document.createElement('div');
            feedback.className = settings.errorFeedbackClass;
            
            // Use custom error message if provided, otherwise use default
            if (field.dataset.errorMessage) {
                feedback.textContent = field.dataset.errorMessage;
            } else {
                feedback.textContent = FormValidator.getDefaultErrorMessage(field);
            }
            
            parent.appendChild(feedback);
        }
        
        return isValid;
    },
    
    // Reset validation state for a form
    resetForm: function(formId) {
        const form = document.getElementById(formId);
        if (!form || !form.validationSettings) return false;
        
        const settings = form.validationSettings;
        const inputs = form.querySelectorAll('input, select, textarea');
        
        inputs.forEach(input => {
            input.classList.remove(settings.errorClass, settings.validClass);
            
            // Remove feedback elements
            const parent = input.parentNode;
            const existingFeedback = parent.querySelectorAll('.' + settings.errorFeedbackClass + ', .' + settings.validFeedbackClass);
            existingFeedback.forEach(el => el.remove());
        });
        
        return true;
    },
    
    // Utility validation methods
    isValidUrl: function(url) {
        try {
            new URL(url);
            return true;
        } catch (e) {
            return false;
        }
    },
    
    isValidEmail: function(email) {
        const re = /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/;
        return re.test(email);
    },
    
    isValidPassword: function(password) {
        // At least 8 characters, with at least one uppercase, one lowercase, and one number
        const re = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[a-zA-Z\d]{8,}$/;
        return re.test(password);
    },
    
    isNumeric: function(value) {
        return !isNaN(parseFloat(value)) && isFinite(value);
    },
    
    isInteger: function(value) {
        return Number.isInteger(Number(value));
    },
    
    // Get default error message based on field type and validation
    getDefaultErrorMessage: function(field) {
        if (field.validity.valueMissing) {
            return 'This field is required';
        } else if (field.validity.typeMismatch) {
            if (field.type === 'email') {
                return 'Please enter a valid email address';
            } else if (field.type === 'url') {
                return 'Please enter a valid URL';
            }
        } else if (field.validity.tooShort) {
            return `Please enter at least ${field.minLength} characters`;
        } else if (field.validity.tooLong) {
            return `Please enter no more than ${field.maxLength} characters`;
        } else if (field.validity.rangeUnderflow) {
            return `Value must be at least ${field.min}`;
        } else if (field.validity.rangeOverflow) {
            return `Value must be no more than ${field.max}`;
        } else if (field.validity.patternMismatch) {
            return 'Please match the requested format';
        } else if (field.dataset.validateUrl !== undefined) {
            return 'Please enter a valid URL';
        } else if (field.dataset.validateEmail !== undefined) {
            return 'Please enter a valid email address';
        } else if (field.dataset.validatePassword !== undefined) {
            return 'Password must be at least 8 characters with at least one uppercase letter, one lowercase letter, and one number';
        } else if (field.dataset.validateMatch) {
            return 'Fields do not match';
        } else if (field.dataset.validateMinLength) {
            return `Please enter at least ${field.dataset.validateMinLength} characters`;
        } else if (field.dataset.validateMaxLength) {
            return `Please enter no more than ${field.dataset.validateMaxLength} characters`;
        } else if (field.dataset.validateNumeric !== undefined) {
            return 'Please enter a valid number';
        } else if (field.dataset.validateInteger !== undefined) {
            return 'Please enter a valid integer';
        } else if (field.dataset.validateMin) {
            return `Value must be at least ${field.dataset.validateMin}`;
        } else if (field.dataset.validateMax) {
            return `Value must be no more than ${field.dataset.validateMax}`;
        }
        
        return 'Invalid value';
    }
};

// Initialize validation for common forms on document ready
document.addEventListener('DOMContentLoaded', function() {
    // Login form validation
    if (document.getElementById('loginForm')) {
        FormValidator.init('loginForm');
    }
    
    // Registration form validation
    if (document.getElementById('registerForm')) {
        FormValidator.init('registerForm');
    }
    
    // Add college form validation
    if (document.getElementById('collegeForm')) {
        FormValidator.init('collegeForm');
    }
    
    // Import colleges form validation
    if (document.getElementById('importForm')) {
        FormValidator.init('importForm');
    }
    
    // User forms validation
    if (document.getElementById('addUserForm')) {
        FormValidator.init('addUserForm');
    }
    
    if (document.getElementById('editUserForm')) {
        FormValidator.init('editUserForm');
    }
});

// Export the FormValidator object
window.FormValidator = FormValidator;