#i was facing considerable difficulty with both python files (app and init_db)
#i used Gemini (with permission) solely for debugging purposes, especially with ensuring i connected everything properly and for a refresher

#import necessary Flask components and database libraries
import os
import psycopg2

#i need the import below to allow for exports as a csv file, along with make_response
import csv
from flask import Flask, make_response, render_template, request, redirect, session, url_for, jsonify, flash #for flashing notifs to the user
from dotenv import load_dotenv
#for the password hash for each user (more security)
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash

#to get current date for filename and possibly scheduling email reminders
from datetime import datetime

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

#pdf export stuff
#COME BACK TO THIS
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
from flask import send_file

#for the scheduled reminders, after pip install apscheduler
from apscheduler.schedulers.background import BackgroundScheduler

#initialize the Flask app
app = Flask(__name__)




#load my credentials from the .env file
load_dotenv()

#secret key (required apparently?) 
#AFTER loading .env since i defined the secret key there
app.secret_key = os.environ['SECRET_KEY']
#function to create a new database connection for each request
def get_db_connection():
    return psycopg2.connect(
        host='drhscit.org', 
        port=5433,
        database=os.environ['DB'],
        user=os.environ['DB_UN'], 
        password=os.environ['DB_PW']
    )

def send_email(to_email, subject, html_content):
    message = Mail(
        from_email=os.environ['SENDGRID_FROM_EMAIL'],
        to_emails=to_email,
        subject=subject,
        html_content=html_content
    )

    try:
        sg = SendGridAPIClient(os.environ['SENDGRID_API_KEY'])
        sg.send(message)
        print(f"Email sent to {to_email}")
    except Exception as e:
        print("SendGrid error:", e)
        

def scheduled_reminders():
    print("Running scheduled reminders...")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute('SELECT email FROM health_accounts WHERE reminders_enabled = TRUE')
    users = cur.fetchall()

    for user in users:
        send_email(
            user[0],
            "Don't forget to log your blood pressure today!",
            """
            <h2>Pulsivity Health Reminder</h2>
            <p>Hello,</p>
            <p>This is your scheduled reminder to log today's blood pressure readings (morning and evening) in the Pulsivity app.</p>

            <p>Regular monitoring can help you track your health and share important information with your healthcare provider.</p>
            <p>Thank you for using Pulsivity!<br>
            The Pulsivity Team</p>
            """
        )

    cur.close()
    conn.close()

#ROUTE: display the main page with the list of previous entries
#altered to check for user login and only show records for the logged-in user
@app.route('/')
def index():
    #checking if the user's logged in
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('welcome'))
    #connect to the DB
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        'SELECT reminders_enabled FROM health_accounts WHERE id = %s', 
        (user_id,)
    )
    reminders_enabled=cur.fetchone()[0]
    
    #fetch all records, newest first
    #cur.execute('SELECT systolic, diastolic, pulse, date_recorded FROM health_stats ORDER BY date_recorded DESC;')
    
    #add 'id' to SELECT query so it can be used in the HTML (THANKS MONIQUE!)
    query = """
        SELECT systolic, diastolic, pulse, date_recorded, id 
        FROM health_stats 
        WHERE user_id = %s 
        ORDER BY date_recorded DESC;
    """
    cur.execute(query, (user_id,))
    records = cur.fetchall()
    
    #clean up the connection
    cur.close()
    conn.close()
    print(records)
    #send the database records to the HTML file for display
    return render_template('index.html', records=records, 
                           reminders_enabled=reminders_enabled)



@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_db_connection()
        cur = conn.cursor()
            
        #ONLY search by email, then check password separately to allow for hashed passwords
        cur.execute('SELECT id, email, password FROM health_accounts WHERE email = %s', (email,))
        user = cur.fetchone()
            
        cur.close()
        conn.close()
            
        #check_password_hash(hashed_password_from_db, plain_text_from_form)
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0] 
            return redirect(url_for('index'))
        else:
            error = "Invalid email or password."
            
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('user_id', None) 
    return redirect(url_for('welcome'))


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if user exists
        cur.execute('SELECT id FROM health_accounts WHERE email = %s', (email,))
        if cur.fetchone():
            error = "An account with that email already exists."
        else:
            # Create account
            hashed_pw = generate_password_hash(password)
            
            # The 'try' block handles the actual database write
            try:
                cur.execute('INSERT INTO health_accounts (email, password) VALUES (%s, %s)', (email, hashed_pw))
                conn.commit()
                cur.close()
                conn.close()
                return redirect(url_for('login'))
            
            # 'Exception as e' catches any crash and stores the error message in 'e'
            except Exception as e:
                error = f"Database error: {e}" 
            
        cur.close()
        conn.close()
            
    return render_template('signup.html', error=error)


#welcome page
@app.route('/welcome')
def welcome():
    return render_template('welcome.html', title="Welcome! | ")

#@app.route('/home')
#def home():
    #return render_template('index.html', title="Home")

#FEBRUARY 28TH, APP ROUTE TO ENABLE REMINDERS
@app.route('/toggle_reminders', methods=['POST'])
def toggle_reminders():
    user_id = session.get('user_id')
    enabled = 'reminders' in request.form

    conn = get_db_connection()
    cur = conn.cursor()
    #running SQL command to update the reminders_enabled column i added
    #in the health_accounts table for the logged-in user
    cur.execute(
        'UPDATE health_accounts SET reminders_enabled = %s WHERE id = %s',
        (enabled, user_id)
    )
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('index'))

@app.route('/run_reminders')
def run_reminders():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute('SELECT email FROM health_accounts WHERE reminders_enabled = TRUE')
    users = cur.fetchall()

    for user in users:
        send_email(
            user[0],
            "Don't forget to log your blood pressure today!",
            """
            <h1>Pulsivity Health Reminder</h2>
            <h2>Hello,</h2>
            <h2>This is your scheduled reminder to log today's blood pressure readings (morning and evening) in the Pulsivity app.</h2>

            <h2>Regular monitoring can help you track your health and share important information with your healthcare provider.</h2>
            <h2>Thank you for using Pulsivity!<br>
            The Pulsivity Team</h2>
            """
        )
    cur.close()
    conn.close()

    return "Reminders sent!"


#FEB 28TH: app route to test email notifs
@app.route('/test_email')
def test_email():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT email FROM health_accounts WHERE id = %s', (user_id,))
    email = cur.fetchone()[0]
    cur.close()
    conn.close()

    send_email(
        email,
        "Pulsivity Test Email",
        "<strong>This is a test email from Pulsivity.</strong>"
    )

    return "Test email sent! Check your inbox."

@app.route('/help')
def help():
    return render_template('help.html', title="Help | ")

#FEBRUARY 19TH, APP ROUTE TO UPDATE CHART
@app.route('/api/health_stats')
def health_stats_api():
    #test
    user_id = session.get('user_id')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT systolic, diastolic, pulse FROM health_stats WHERE user_id=%s ORDER BY id', (user_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    data = [{'systolic': r[0], 'diastolic': r[1], 'pulse': r[2]} for r in rows]
    return jsonify(data)

@app.route('/export')
def export_csv():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT date_recorded, systolic, diastolic, pulse FROM health_stats WHERE user_id = %s ORDER BY date_recorded;', (user_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    #create response from csv
    output = "Date,Systolic,Diastolic,Pulse\n"
    for row in rows:
        output += f"{row[0]},{row[1]},{row[2]},{row[3]}\n"

    #generates filename with current date (for easier organization for users)
    today_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"blood_pressure_log_{today_str}.csv"

    response = make_response(output)
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-Type"] = "text/csv"
    return response

#APRIL 9TH, APP ROUTE TO EXPORT PDF (NOT WORKING YET)
@app.route('/export_pdf')
def export_pdf():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        'SELECT date_recorded, systolic, diastolic, pulse FROM health_stats WHERE user_id = %s ORDER BY date_recorded;',
        (user_id,)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    #create PDF in memory
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)

    #title
    p.setFont("Courier-Bold", 16)
    p.drawString(50, 750, "Pulsivity Health Report")

    #date
    today_str = datetime.now().strftime("%Y-%m-%d")
    p.setFont("Courier", 12)
    p.drawString(50, 730, f"Export Date: {today_str}")

    #table headers
    y = 700
    p.drawString(30, y, "Date")
    p.drawString(280, y, "SYS")
    p.drawString(320, y, "DIA")
    p.drawString(360, y, "Pulse")

    #data rows
    y -= 20
    for row in rows:
        p.drawString(30, y, str(row[0]))
        p.drawString(280, y, str(row[1]))
        p.drawString(320, y, str(row[2]))
        p.drawString(360, y, str(row[3]))
        y -= 20

    #start new page if too long
    if y < 50:
        p.showPage()
        y = 750

    p.save()

    buffer.seek(0)

    filename = f"blood_pressure_report_{today_str}.pdf"

    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )



#MARCH 19TH, APP ROUTE TO DELETE ACCOUNT
@app.route('/delete_account', methods=['POST'])
def delete_account():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    
    #delete the user's health stats first to avoid foreign key issues
    cur.execute('DELETE FROM health_stats WHERE user_id = %s', (user_id,))
    
    #then delete the user's account
    cur.execute('DELETE FROM health_accounts WHERE id = %s', (user_id,))
    
    conn.commit()
    cur.close()
    conn.close()
    
    session.pop('user_id', None) 
    return redirect(url_for('welcome'))

#used POST method for safer deletions via form buttons
@app.route('/delete/<int:id>', methods=['POST'])
def del_record(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM health_stats WHERE id = %s', (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('index'))

@app.route('/add', methods=['POST'])
def add_record():
    #retrieves the columns from the table in SQL
    sys = request.form['systolic']
    dia = request.form['diastolic']
    pul = request.form['pulse']

    #connect to the DB to save data
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('INSERT INTO health_stats (systolic, diastolic, pulse, user_id) VALUES (%s, %s, %s, %s)',
                (sys, dia, pul, session['user_id']))
    
    #save the new row permanently
    conn.commit()
    
    #bye bye
    cur.close()
    conn.close()
    
    #back to the home page to see their new entry in the list
    return redirect(url_for('index'))


if __name__ == '__main__':
    scheduler = BackgroundScheduler()

    #morning reminder (8 AM)
    scheduler.add_job(scheduled_reminders, 'cron', hour=8, minute=0)

    
    #evening reminder (8 PM)
    scheduler.add_job(scheduled_reminders, 'cron', hour=20, minute=2)

    scheduler.start()
    app.run(host="0.0.0.0", debug=True)

