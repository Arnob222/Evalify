from django.shortcuts import render

def home(request):
    return render(request, 'homepage.html')


def sign_up_html(request):
    return render(request, "sign_up.html")


def sign_in_html(request):
    return render(request, "sign_in.html")