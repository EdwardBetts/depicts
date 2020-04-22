from flask import current_app
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
import smtplib

def send_mail(subject, body):
    app = current_app
    mail_to = app.config['ADMIN_EMAIL']
    mail_from = app.config['MAIL_FROM']
    msg = MIMEText(body, 'plain', 'UTF-8')

    msg['Subject'] = subject
    msg['To'] = mail_to
    msg['From'] = mail_from
    msg['Date'] = formatdate()
    msg['Message-ID'] = make_msgid()

    s = smtplib.SMTP(app.config['SMTP_HOST'])
    s.sendmail(mail_from, [mail_to], msg.as_string())
    s.quit()
