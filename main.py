from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import sqlite3
from datetime import datetime, timedelta
import qrcode
from fastapi.staticfiles import StaticFiles
import os

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # payments
    c.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        item TEXT,
        amount REAL,
        datetime TEXT
    )
    """)

    # memberships
    c.execute("""
    CREATE TABLE IF NOT EXISTS memberships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        expiry TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT * FROM transactions ORDER BY id DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"transactions": rows}
    )

@app.post("/pay", response_class=HTMLResponse)
def pay(request: Request, name: str = Form(...), item: str = Form(...)):

    amount = {
        "Monthly": 1500,
        "Day Pass": 200,
        "Drink": 50
    }[item]

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # save transaction
    c.execute("""
        INSERT INTO transactions (name, item, amount, datetime)
        VALUES (?, ?, ?, ?)
    """, (name, item, amount, datetime.now().strftime("%Y-%m-%d %H:%M")))

    qr_path = None

    # 👇 ONLY create membership for Monthly
    if item == "Monthly":
        expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

        c.execute("""
            INSERT INTO memberships (name, expiry)
            VALUES (?, ?)
        """, (name, expiry))

        member_id = c.lastrowid

        BASE_URL = "https://gym-pos-system.onrender.com"

        url = f"{BASE_URL}/check/{member_id}"
        img = qrcode.make(url)
        img.save(f"static/{member_id}.png")

        qr_path = f"/static/{member_id}.png"

    conn.commit()

    # reload transaction table
    c.execute("SELECT * FROM transactions ORDER BY id DESC LIMIT 10")
    rows = c.fetchall()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "transactions": rows,
            "message": f"{name} paid for {item}",
            "qr": qr_path
        }
    )
@app.get("/check/{member_id}", response_class=HTMLResponse)
def check_user(request: Request, member_id: int):

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT name, expiry FROM memberships WHERE id=?", (member_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        status = "❌ Not Found"
        name = None
    else:
        name, expiry = row
        today = datetime.now().strftime("%Y-%m-%d")

        if expiry >= today:
            status = "✅ Valid Membership"
        else:
            status = "❌ Expired"

    return templates.TemplateResponse(
    request=request,
    name="check.html",
    context={
        "status": status,
        "name": name,
        "auto_return": True
    }
)
@app.get("/members", response_class=HTMLResponse)
def members(request: Request):

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT id, name, expiry FROM memberships ORDER BY id DESC")
    rows = c.fetchall()

    conn.close()

    # process status
    today = datetime.now().strftime("%Y-%m-%d")

    members_list = []
    for m in rows:
        member_id, name, expiry = m

        if expiry >= today:
            status = "✅ Valid"
        else:
            status = "❌ Expired"

        members_list.append({
            "id": member_id,
            "name": name,
            "expiry": expiry,
            "status": status
        })

    return templates.TemplateResponse(
        request=request,
        name="members.html",
        context={"members": members_list}
    )
@app.post("/renew/{member_id}")
def renew(member_id: int):

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # get current expiry
    c.execute("SELECT expiry FROM memberships WHERE id=?", (member_id,))
    row = c.fetchone()

    today=datetime.now()
    if row:
        expiry = datetime.strptime(row[0], "%Y-%m-%d")

        # extend 30 days
        if expiry < today:
            new_expiry = today + timedelta(days=30)
        else:
            new_expiry = expiry + timedelta(days=30)

        c.execute("""
            UPDATE memberships
            SET expiry=?
            WHERE id=?
        """, (new_expiry.strftime("%Y-%m-%d"), member_id))

        conn.commit()

    conn.close()

    return RedirectResponse(url="/members", status_code=303)

@app.get("/scan", response_class=HTMLResponse)
def scan(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="scan.html",
        context={}
    )

