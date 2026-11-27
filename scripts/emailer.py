#!/usr/bin/env python3
"""Envío del dossier por correo electrónico (SMTP corporativo o Gmail)."""
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from jinja2 import Environment, FileSystemLoader, select_autoescape

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(os.path.dirname(BASE_DIR), "templates")


def send_report(settings, meta, report, items, log=print):
    """Envía el correo con el resumen ejecutivo y el PDF adjunto.

    Credenciales por variables de entorno (secretos de GitHub Actions):
      SMTP_HOST, SMTP_PORT (def. 587), SMTP_USER, SMTP_PASSWORD,
      EMAIL_FROM (opcional), EMAIL_TO (lista separada por comas; si falta, admin_email).
    """
    if not settings.get("email_enabled", True):
        log("  [email] Envío desactivado en settings.")
        return

    host = os.environ.get("SMTP_HOST", "")
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    port = int(os.environ.get("SMTP_PORT", "587"))
    sender = os.environ.get("EMAIL_FROM", "") or user
    recipients = os.environ.get("EMAIL_TO", "") or settings.get("admin_email", "")

    if not (host and user and password and recipients):
        log("  [email] Faltan credenciales SMTP o destinatarios: correo no enviado.")
        return

    counts = report["counts"]
    top5 = items[:5]
    pages_url = settings.get("pages_url", "")
    dossier_url = pages_url + "latest/index.html" if pages_url else ""

    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )
    html_body = env.get_template("email.html.j2").render(
        meta=meta,
        counts=counts,
        top5=top5,
        dossier_url=dossier_url,
    )

    subject = f"{settings.get('email_subject', '[DOSSIER PRESIDENCIA RENFE]')} {meta['tipo']} · {meta['created']}"

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = formataddr(("Dossier Presidencia RENFE", sender))
    msg["To"] = recipients
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if report.get("pdf_path") and os.path.exists(report["pdf_path"]):
        with open(report["pdf_path"], "rb") as fh:
            part = MIMEApplication(fh.read(), _subtype="pdf")
            part.add_header("Content-Disposition", "attachment", filename="dossier.pdf")
            msg.attach(part)

    try:
        with smtplib.SMTP(host, port, timeout=60) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(user, password)
            smtp.sendmail(sender, [r.strip() for r in recipients.split(",") if r.strip()], msg.as_string())
        log(f"  [email] Correo enviado a {recipients}.")
    except Exception as exc:
        log(f"  [email] Aviso: fallo al enviar el correo: {exc}")
