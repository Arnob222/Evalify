document.addEventListener('DOMContentLoaded', () => {
    // Password toggle
    const toggle = document.getElementById('togglePass');
    const field  = document.getElementById('passwordField');
    if (toggle && field) {
        field.type = 'password';
        toggle.textContent = 'Show';
        toggle.addEventListener('click', () => {
            const show = field.type === 'password';
            field.type = show ? 'text' : 'password';
            toggle.textContent = show ? 'Hide' : 'Show';
        });
    }

    // Fade-in
    document.querySelectorAll('.left-body > *, .form-card > *').forEach((el, i) => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(12px)';
        el.style.transition = `opacity .5s ease ${i * 60}ms, transform .5s ease ${i * 60}ms`;
        setTimeout(() => {
            el.style.opacity = '1';
            el.style.transform = 'translateY(0)';
        }, 50);
    });
});