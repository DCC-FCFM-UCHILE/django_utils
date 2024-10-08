import json
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import login as custom_login
from django.contrib.auth import logout as custom_logout
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse

from sso.utils import error, log


def index(request):
    if request.user.is_authenticated:
        if hasattr(settings, "SSO_LOGIN_VIEW") and settings.SSO_LOGIN_VIEW:
            return redirect(reverse(settings.SSO_LOGIN_VIEW))
        elif hasattr(settings, "SSO_LOGIN_URL") and settings.SSO_LOGIN_URL:
            return redirect(settings.SSO_LOGIN_URL)

        if request.META["SCRIPT_NAME"]:
            return redirect(f"{request.META['SCRIPT_NAME']}/")
        return redirect("/")

    if hasattr(settings, "SSO_APP_URL"):
        return redirect(f"{settings.SSO_URL}?app={settings.SSO_APP}&url={settings.SSO_APP_URL}")
    return redirect(f"{settings.SSO_URL}?app={settings.SSO_APP}")


def login(request):
    ip_address = request.META.get("HTTP_X_FORWARDED_FOR", "0xL").split(", ")[0]
    username = request.GET.get("username", None)
    secret = request.GET.get("secret", None)

    ldata = {"ip_address": ip_address, "username": username, "secret": secret}

    if not username or not secret:
        # TODO: crear un template para este error
        error("usuario o secret no especificado", ldata)
        return HttpResponseRedirect(reverse("sso:index"))

    user = get_user(username, secret)
    if not user:
        # TODO: crear un template para este error
        error("error al inicializar el usuario", ldata)
        return HttpResponseRedirect(reverse("sso:index"))

    if not user.is_active:
        log("usuario encontrado pero no activo", ldata)
        return HttpResponseRedirect(reverse("sso:unauthorized"))

    log("usuario autenticado y autorizado", ldata)
    custom_login(request, user)
    return HttpResponseRedirect(reverse("sso:index"))


def logout(request):
    username = None
    if request.user.is_authenticated:
        username = request.user.username
    ip_address = request.META.get("HTTP_X_FORWARDED_FOR", "0xL").split(", ")[0]
    ldata = {"ip_address": ip_address, "username": request.user.username}

    if not username:
        error("intenta logout sin estar logeado", ldata)
    else:
        log("logout usuario", ldata)

    custom_logout(request)

    if hasattr(settings, "SSO_LOGOUT_URL") and settings.SSO_LOGOUT_URL:
        return redirect(settings.SSO_LOGOUT_URL)
    elif hasattr(settings, "SSO_LOGOUT_VIEW") and settings.SSO_LOGOUT_VIEW:
        return redirect(reverse(settings.SSO_LOGOUT_VIEW))
    return redirect("https://portal.dcc.uchile.cl")


def unauthorized(request):
    html = """
<!doctype html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.0-beta1/dist/css/bootstrap.min.css" rel="stylesheet"
          integrity="sha384-giJF6kkoqNQ00vy+HMDP7azOuL0xtbfIcaT9wjKHr8RbDVddVHyTfAAsrekwKmP1" crossorigin="anonymous">
    <title>Portal Servicios DCC</title>
</head>
<style>
    body {background-color: #333; color: white;}
    .logo {width: 215px; height: 110px; margin: 50px;}
    .wrapper { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%);}
</style>
<body>
<div class="wrapper">
    <center>
        <img class="logo" src="https://dcc.uchile.cl/static/images/logo.svg">
        <br />
        <div class="alert alert-danger" role="alert">
          Se ha autenticado correctamente pero no está autorizado para utilizar esta App.<br />
          Contacte al Área de Desarrollo de Aplicaciones
          (<a href="mailto:ati@dcc.uchile.cl">ati@dcc.uchile.cl</a>) para solicitar acceso.
        </div>
    </center>
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.0.0-beta1/dist/js/bootstrap.bundle.min.js"
        integrity="sha384-ygbV9kiqUc6oa4msXn9868pTtWMgiQaeYH7/t7LECLbyPA2x65Kgf80OJFdroafW"
        crossorigin="anonymous"></script>
</body>
</html>
"""
    return HttpResponse(html)


# FUNCIONES
def get_user(username, secret):
    data = get_data(username, secret)
    user = None

    if "valid" in data and data["valid"]:
        User = get_user_model()

        user, created = User.objects.update_or_create(
            username=data["username"],
            defaults={
                "email": data["persona"]["email"] if data["persona"] and "email" in data["persona"] else data["email"],
                "first_name": f"{data['first_name']}",
                "last_name": f"{data['last_name']}",
            },
        )

        if created:
            user.is_active = settings.SSO_AUTH
            user.save()

        # si usa User custom, se extiende la data del mismo
        if "users.apps.UsersConfig" in settings.INSTALLED_APPS and "persona" in data:
            if "alias" in data["persona"]:
                user.alias = data["persona"]["alias"]
            if "foto" in data["persona"]:
                user.url_foto = data["persona"]["foto"]
            if "email" in data["persona"]:
                user.email = data["persona"]["email"]
            user.data = data
            user.save()

    return user


def get_data(username, secret):
    data = {"valid": False}
    params = {"app": settings.SSO_APP, "secret": secret, "username": username}
    url = f"{settings.SSO_URL}/is_valid?{urlencode(params)}"

    ldata = {"url": url}
    try:
        data = json.loads(urlopen(url).read())
    except Exception:
        error("error al intentar obtener data del usuario desde el portal", ldata)
    log("data de usuario obtenida desde el portal", ldata)

    return data
