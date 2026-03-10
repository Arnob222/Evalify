document.getElementById('togglePass').addEventListener('click', function() {
    const passField = document.getElementById('passwordField');
    if (passField.type === "password") {
        passField.type = "text";
        this.textContent = "👁 Show";
    } else {
        passField.type = "password";
        this.textContent = "👁 Hide";
    }
});