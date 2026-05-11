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

    // Password strength
    const fill = document.getElementById('strengthFill');
    const hint = document.getElementById('strengthHint');
    if (field && fill && hint) {
        field.addEventListener('input', () => {
            const v = field.value;
            let score = 0;
            if (v.length >= 8)           score++;
            if (/[A-Z]/.test(v))         score++;
            if (/[0-9]/.test(v))         score++;
            if (/[^A-Za-z0-9]/.test(v))  score++;

            const levels = [
                { w: '0%',   bg: 'transparent', msg: 'Use letters, numbers & symbols' },
                { w: '33%',  bg: '#ff6b6b',     msg: 'Weak — add more variety'        },
                { w: '66%',  bg: '#f59e0b',     msg: 'Medium — almost there'          },
                { w: '100%', bg: '#00c896',     msg: 'Strong password ✓'              },
            ];
            const lvl = score === 0 ? 0 : score <= 1 ? 1 : score <= 2 ? 2 : 3;
            fill.style.width      = levels[lvl].w;
            fill.style.background = levels[lvl].bg;
            hint.textContent      = levels[lvl].msg;
            hint.style.color      = lvl === 3 ? '#00c896' : '';
        });
    }

    // Fade-in
    document.querySelectorAll('.left-body > *, .form-card > *').forEach((el, i) => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(12px)';
        el.style.transition = `opacity .5s ease ${i * 55}ms, transform .5s ease ${i * 55}ms`;
        setTimeout(() => {
            el.style.opacity = '1';
            el.style.transform = 'translateY(0)';
        }, 50);
    });
});