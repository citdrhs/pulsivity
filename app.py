#i was facing considerable difficulty with both python files (app and init_db)
#i used Gemini (with permission) solely for debugging purposes, especially with ensuring i connected everything properly and for a refresher

#import necessary Flask components and database libraries
import os
import psycopg2
from flask import Flask, render_template, request, redirect, session, url_for, jsonify, flash #for flashing notifs to the user
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

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
        'SELECT reminders_enables FROM health_accounts WHERE id = %s', 
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
    if request.method == 'POST':
        email = request.form.get('email')
        #password hash for security purposes
        password = generate_password_hash(request.form.get('password'))
        
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute('INSERT INTO health_accounts (email, password) VALUES (%s, %s)', (email, password))
            conn.commit()
            return redirect(url_for('login'))
        except Exception as e:
            return f"Error: {e}" 
        finally:
            cur.close()
            conn.close()
            
    return render_template('signup.html')

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
        'UPDATE health_accounts SET reminders_enables = %s WHERE id = %s',
        (enabled, user_id)
    )
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('index'))

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
    app.run(debug=True)

