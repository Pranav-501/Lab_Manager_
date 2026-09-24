# IT Lab Management System

A complete beginner-friendly capstone web application built with Python Flask, SQLite, HTML, CSS and JavaScript.

## Features
- Admin and Staff login
- Dashboard with live statistics
- Lab management
- Computer/asset inventory
- Equipment inventory
- Lab booking requests and approval
- Complaint/ticket management
- Maintenance scheduling
- User management
- Responsive UI
- SQLite database automatically created and seeded

## Run in VS Code
1. Install Python 3.11+.
2. Open this project folder in VS Code.
3. Open Terminal -> New Terminal.
4. Run:
   `python -m venv venv`
5. Windows:
   `venv\Scripts\activate`
6. Install packages:
   `pip install -r requirements.txt`
7. Start:
   `python app.py`
8. Open: http://127.0.0.1:5000

## Demo accounts
Admin: admin@itlab.local / admin123
Staff: staff@itlab.local / staff123

For a real deployment, passwords should be hashed and the secret key should be stored in an environment variable.
