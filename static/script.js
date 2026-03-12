// ==========================================
// 1. Explore Rooms Redirect Logic
// ==========================================
function redirectToLogin() {
    const isLoggedIn = document.body.classList.contains('logged-in');
    
    if (isLoggedIn) {
        window.location.href = '/available_rooms';
    } else {
        window.location.href = '/login_page';
    }
}

// ==========================================
// 2. Smooth Scroll for Nav Links
// ==========================================
function smoothScroll() {
    const links = document.querySelectorAll('a[href^="/#"]');
    
    if (links.length > 0) {
        links.forEach(link => {
            link.addEventListener('click', function(e) {
                const href = this.getAttribute('href');
                const hash = href.split('#')[1];
                
                if (window.location.pathname === '/') {
                    e.preventDefault();
                    const target = document.getElementById(hash);
                    if (target) {
                        target.scrollIntoView({ behavior: 'smooth' });
                    }
                } else {
                    window.location.href = href;
                }
            });
        });
    }

    // Scroll to hash on page load
    const hash = window.location.hash;
    if (hash) {
        const target = document.getElementById(hash.substring(1));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth' });
        }
    }
}

// ==========================================
// 3. Profile Dropdown Menu Logic
// ==========================================
function toggleMenu() {
    const dropdown = document.getElementById('dropdownMenu');
    if (dropdown) {
        dropdown.classList.toggle('show');
    }
}

function closeDropdownOnOutsideClick(event) {
    const profileContainer = document.querySelector('.profile-container');
    const dropdown = document.getElementById('dropdownMenu');

    if (profileContainer && dropdown) {
        if (!profileContainer.contains(event.target) && !dropdown.contains(event.target)) {
            dropdown.classList.remove('show');
        }
    }
}

// ==========================================
// Professional Modal Functions
// ==========================================

function showModal(type, title, message) {
    const modal = document.getElementById('customModal');
    const modalBox = document.getElementById('modalBox');
    const modalIcon = document.getElementById('modalIcon');
    const modalIconType = document.getElementById('modalIconType');
    const modalTitle = document.getElementById('modalTitle');
    const modalMessage = document.getElementById('modalMessage');
    
    // Set icon based on type
    modalIcon.className = 'modal-icon ' + type;
    
    // Set icon content
    const icons = {
        success: '<i class="fas fa-check"></i>',
        error: '<i class="fas fa-times"></i>',
        warning: '<i class="fas fa-exclamation-triangle"></i>',
        info: '<i class="fas fa-info-circle"></i>'
    };
    modalIconType.innerHTML = icons[type] || icons.info;
    
    // Set title and message
    modalTitle.textContent = title;
    modalMessage.textContent = message;
    
    // Show modal
    modal.classList.add('show');
    
    // Add shake for error
    if (type === 'error') {
        modalBox.classList.add('shake');
        setTimeout(() => modalBox.classList.remove('shake'), 500);
    }
}

function closeModal() {
    const modal = document.getElementById('customModal');
    modal.classList.remove('show');
}

// Close on overlay click
document.getElementById('customModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeModal();
    }
});

// Close on Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeModal();
    }
});

// ==========================================
// Form Validation (Professional)
// ==========================================

function validateForm() {
    const email = document.querySelector('input[name="email"]').value.trim();
    const name = document.querySelector('input[name="name"]').value.trim();
    const password = document.querySelector('input[name="password"]').value;
    const confirmPassword = document.querySelector('input[name="confirm_password"]');
    
    // Email pattern validation
    const emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    
    if (!emailPattern.test(email)) {
        showModal('error', 'Invalid Email!', 'Please enter a valid email address (e.g., name@example.com)');
        return false;
    }
    
    if (name.length < 2) {
        showModal('error', 'Invalid Name!', 'Name must be at least 2 characters long');
        return false;
    }
    
    if (password.length < 6) {
        showModal('error', 'Weak Password!', 'Password must be at least 6 characters long');
        return false;
    }
    
    // Check password match if confirm password field exists
    if (confirmPassword && confirmPassword.value) {
        if (password !== confirmPassword.value) {
            showModal('error', 'Password Mismatch!', 'Password and Confirm Password do not match');
            return false;
        }
    }
    
    // Show success message (optional)
    // showModal('success', 'Validating...', 'Please wait while we process your registration');
    
    return true;
}

// ==========================================
// Initialize Everything
// ==========================================

document.addEventListener('DOMContentLoaded', function() {
    // Smooth scroll
    smoothScroll();
    
    // Close dropdown on outside click
    document.addEventListener('click', closeDropdownOnOutsideClick);
    
    // Password match validation
    checkPasswordMatch();
});
function searchTable() {
    const input = document.getElementById('searchInput');
    const filter = input.value.toLowerCase();
    const table = document.getElementById('dataTable');
    const tr = table.getElementsByTagName('tr');

    for (let i = 1; i < tr.length; i++) {
        let visible = false;
        const td = tr[i].getElementsByTagName('td');
        for (let j = 0; j < td.length; j++) {
            if (td[j]) {
                const txtValue = td[j].textContent || td[j].innerText;
                if (txtValue.toLowerCase().indexOf(filter) > -1) {
                    visible = true;
                }
            }
        }
        tr[i].style.display = visible ? '' : 'none';
    }
}
//pop up for 3 sec
setTimeout(function(){

    const flash = document.querySelector(".flash-container");

    if(flash){
        flash.style.display = "none";
    }

},3000);
// ================= Role-based Secret Key =================
const roleSelect = document.querySelector('select[name="role"]');
const secretDiv = document.getElementById('secretKeyDiv');
const secretInput = secretDiv.querySelector('input');

roleSelect.addEventListener('change', () => {
    if(roleSelect.value === 'admin' || roleSelect.value === 'warden') {
        secretDiv.style.display = 'block';
        secretInput.required = true; // Make secret key mandatory
    } else {
        secretDiv.style.display = 'none';
        secretInput.required = false;
        secretInput.value = ''; // Clear input when hidden
    }
});

// ================= Password Match Check =================
const password = document.getElementById("password");
const confirmPassword = document.getElementById("confirmPassword");
const message = document.getElementById("passwordMessage");
const submitBtn = document.querySelector("button[type='submit']");

function checkPassword() {
    const pass = password.value;
    const confirm = confirmPassword.value;

    if(confirm === "") {
        confirmPassword.classList.remove("password-match","password-mismatch");
        message.textContent = "";
        submitBtn.disabled = false;
        return;
    }

    if(pass === confirm) {
        confirmPassword.classList.add("password-match");
        confirmPassword.classList.remove("password-mismatch");
        message.textContent = "Password match ✓";
        message.style.color = "green";
        submitBtn.disabled = false;
    } else {
        confirmPassword.classList.add("password-mismatch");
        confirmPassword.classList.remove("password-match");
        message.textContent = "Password do not match";
        message.style.color = "red";
        submitBtn.disabled = true;
    }
}

password.addEventListener("input", checkPassword);
confirmPassword.addEventListener("input", checkPassword);

