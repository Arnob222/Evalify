document.addEventListener('DOMContentLoaded', () => {
    const facultyCard = document.getElementById('facultyCard');
    const studentCard = document.getElementById('studentCard');

    // Simple interaction to show system mode switching
    facultyCard.addEventListener('click', () => {
        console.log("Switching to Faculty Workspace...");
        alert("Entering Faculty Mode: Assessment Tools loading.");
    });

    studentCard.addEventListener('click', () => {
        console.log("Switching to Student Workspace...");
        alert("Entering Student Mode: Results and CLO Tracking loading.");
    });

    // Add a hover animation for the feature cards
    const features = document.querySelectorAll('.feature-item');
    features.forEach(card => {
        card.addEventListener('mouseenter', () => {
            card.style.borderColor = '#00E5FF';
            card.style.transform = 'translateY(-5px)';
        });
        card.addEventListener('mouseleave', () => {
            card.style.borderColor = 'rgba(148, 163, 184, 0.2)';
            card.style.transform = 'translateY(0)';
        });
    });
});