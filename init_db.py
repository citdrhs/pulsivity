#I was facing considerable difficulty with initializing both Python files (app and init_db).
#I used Gemini (with permission) solely for debugging purposes, especially 
#with ensuring i connected everything properly and for a refresher.

import os
#import psycopg2 to interact with the PostgreSQL database
import psycopg2
#import load_dotenv to read the .env file
#i had to run pip install python-dotenv on PowerShell
from dotenv import load_dotenv

load_dotenv()

def init_db():
    #connection to credentials from .env
    conn = psycopg2.connect(
        host='drhscit.org',
        database=os.environ['DB'],
        user=os.environ['DB_UN'],
        password=os.environ['DB_PW']
    )
    
    #cursor object to execute SQL commands
    cur = conn.cursor()
    
    #delete old tables if they exist
    cur.execute('DROP TABLE IF EXISTS health_stats;')
    cur.execute('DROP TABLE IF EXISTS health_accounts;')
    
    #create table with columns for BP and pulse; i had to copy paste the code into SQL
    #serial PRIMARY KEY:unique ID for every entry
    #integer NOT NULL: no null allowed; whole number only
    #timestamp: automatically records the exact time the user clicks "Save"

    #add something for user id; to differentiate between users - FOREIGN KEY
    #check drive for authorization - can't see someone else's private info !
    cur.execute('''
        CREATE TABLE health_stats (
        
            id serial PRIMARY KEY,
            systolic integer NOT NULL,
            diastolic integer NOT NULL,
            pulse integer NOT NULL,
            date_recorded timestamp DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    cur.execute('''
        CREATE TABLE health_accounts (
            id serial PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        );
    ''')
    
    conn.commit()
    
    #bye byeee
    cur.close()
    conn.close()
    print("initialized with health_stats table.")

if __name__ == '__main__':
    init_db()
