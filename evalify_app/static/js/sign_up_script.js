const form = document.getElementById("signupForm");

const nameField = document.getElementById("profileName");
const emailField = document.getElementById("email");
const passwordField = document.getElementById("passwordField");
const strengthText = document.getElementById("passwordStrength");

/* PASSWORD SHOW / HIDE */

document.getElementById('togglePass').addEventListener('click', function(){

if(passwordField.type === "password"){
passwordField.type = "text";
this.textContent = "👁 Show";
}
else{
passwordField.type = "password";
this.textContent = "👁 Hide";
}

});


/* PASSWORD STRENGTH CHECK */

passwordField.addEventListener("input", function(){

let value = passwordField.value;

let strength = 0;

if(value.length >= 8) strength++;

if(value.match(/[a-z]/)) strength++;

if(value.match(/[A-Z]/)) strength++;

if(value.match(/[0-9]/)) strength++;

if(value.match(/[^a-zA-Z0-9]/)) strength++;

switch(strength){

case 0:
case 1:
strengthText.textContent = "Weak Password";
strengthText.style.color = "red";
break;

case 2:
strengthText.textContent = "Weak Password";
strengthText.style.color = "red";
break;

case 3:
strengthText.textContent = "Medium Password";
strengthText.style.color = "orange";
break;

case 4:
strengthText.textContent = "Strong Password";
strengthText.style.color = "lime";
break;

case 5:
strengthText.textContent = "Very Strong Password";
strengthText.style.color = "cyan";
break;

}

});


/* FORM VALIDATION */

form.addEventListener("submit", function(e){

let name = nameField.value.trim();
let email = emailField.value.trim();
let password = passwordField.value.trim();
let role = document.querySelector('input[name="role"]:checked');

if(name === ""){
alert("Profile Name is required");
e.preventDefault();
return;
}

if(email === ""){
alert("Email is required");
e.preventDefault();
return;
}

let emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

if(!emailPattern.test(email)){
alert("Invalid email format");
e.preventDefault();
return;
}

if(password.length < 8){
alert("Password must be at least 8 characters");
e.preventDefault();
return;
}

if(!role){
alert("Please select Student or Faculty");
e.preventDefault();
return;
}

});