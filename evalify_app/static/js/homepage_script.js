document.addEventListener('DOMContentLoaded', () => {

    /* staggered fade-up for hero left */
    ['.badge', 'h1', '.description', '.hero-cta'].forEach((sel, i) => {
        const el = document.querySelector(sel);
        if (!el) return;
        el.style.opacity = '0';
        el.style.transform = 'translateY(16px)';
        el.style.transition = `opacity .55s ease, transform .55s ease`;
        setTimeout(() => {
            el.style.opacity = '1';
            el.style.transform = 'translateY(0)';
        }, 80 + i * 90);
    });

    /* panel cards */
    document.querySelectorAll('.panel-card').forEach((el, i) => {
        el.style.opacity = '0';
        el.style.transform = 'translateX(18px)';
        el.style.transition = `opacity .5s ease, transform .5s ease`;
        setTimeout(() => {
            el.style.opacity = '1';
            el.style.transform = 'translateX(0)';
        }, 380 + i * 110);
    });

    /* stats / mode / features */
    [...document.querySelectorAll('.stats-bar, .mode-card, .feature-item')]
        .forEach((el, i) => {
            el.style.opacity = '0';
            el.style.transform = 'translateY(14px)';
            el.style.transition = `opacity .5s ease, transform .5s ease`;
            setTimeout(() => {
                el.style.opacity = '1';
                el.style.transform = 'translateY(0)';
            }, 650 + i * 70);
        });

    /* safety net — ensure all animated elements are visible */
    setTimeout(() => {
        document.querySelectorAll('.badge, h1, .description, .hero-cta, .panel-card, .stats-bar, .mode-card, .feature-item').forEach(el => {
            el.style.opacity = '1';
            el.style.transform = 'translateY(0)';
        });
    }, 2500);
});
