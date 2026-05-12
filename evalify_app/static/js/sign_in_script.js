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
        el.style.transition = `opacity .5s ease, transform .5s ease`;
        setTimeout(() => {
            el.style.opacity = '1';
            el.style.transform = 'translateY(0)';
        }, 80 + i * 60);
    });

    // Safety net — ensure all elements are visible
    setTimeout(() => {
        document.querySelectorAll('.left-body > *, .form-card > *').forEach(el => {
            el.style.opacity = '1';
            el.style.transform = 'translateY(0)';
        });
    }, 2000);
});
