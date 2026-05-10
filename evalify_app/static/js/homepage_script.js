document.addEventListener('DOMContentLoaded', () => {

    /* staggered fade-up for hero left */
    ['.badge', 'h1', '.description', '.hero-cta'].forEach((sel, i) => {
        const el = document.querySelector(sel);
        if (!el) return;
        el.style.cssText += `opacity:0;transform:translateY(16px);
            transition:opacity .55s ease ${i*90}ms,transform .55s ease ${i*90}ms`;
        setTimeout(() => { el.style.opacity='1'; el.style.transform='translateY(0)'; }, 60);
    });

    /* panel cards */
    document.querySelectorAll('.panel-card').forEach((el, i) => {
        el.style.cssText += `opacity:0;transform:translateX(18px);
            transition:opacity .5s ease ${300+i*110}ms,transform .5s ease ${300+i*110}ms`;
        setTimeout(() => { el.style.opacity='1'; el.style.transform='translateX(0)'; }, 60);
    });

    /* stats / mode / features */
    [...document.querySelectorAll('.stats-bar, .mode-card, .feature-item')]
        .forEach((el, i) => {
            el.style.cssText += `opacity:0;transform:translateY(14px);
                transition:opacity .5s ease ${600+i*70}ms,transform .5s ease ${600+i*70}ms`;
            setTimeout(() => { el.style.opacity='1'; el.style.transform='translateY(0)'; }, 60);
        });
});