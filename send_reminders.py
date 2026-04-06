import psycopg2
import os
from datetime import date
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    return psycopg2.connect(
        host='drhscit.org',
        database=os.environ['DB'],
        user=os.environ['DB_UN'],
        password=os.environ['DB_PW']
    )

def send_email(to_email, subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = os.environ['EMAIL_USER']
    msg['To'] = to_email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(os.environ['EMAIL_USER'], os.environ['EMAIL_PASS'])
        server.send_message(msg)

conn = get_db_connection()
cur = conn.cursor()

cur.execute("""
    SELECT a.id, a.email
    FROM health_accounts a
    WHERE a.reminders_enabled = TRUE
    AND NOT EXISTS (
        SELECT 1
        FROM health_stats h
        WHERE h.user_id = a.id
        AND DATE(h.date_recorded) = CURRENT_DATE
    )
""")

users = cur.fetchall()

for user_id, email in users:
    send_email(
        email,
        "Pulsivity Reminder",
        "You haven’t logged your health data today. Please log your reading."
    )

cur.close()
conn.close()