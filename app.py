import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from sqlalchemy import create_engine, text

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///empire.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

def init_db():
    with engine.begin() as con:
        if "postgresql" in DATABASE_URL:
            con.execute(text("""CREATE TABLE IF NOT EXISTS announcements (
                id SERIAL PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,
                created_at TEXT NOT NULL, pinned INTEGER DEFAULT 0)"""))
            con.execute(text("""CREATE TABLE IF NOT EXISTS members (
                id SERIAL PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
                code TEXT DEFAULT '', special_name TEXT DEFAULT '')"""))
        else:
            con.execute(text("""CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, body TEXT NOT NULL,
                created_at TEXT NOT NULL, pinned INTEGER DEFAULT 0)"""))
            con.execute(text("""CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, role TEXT NOT NULL,
                code TEXT DEFAULT '', special_name TEXT DEFAULT '')"""))

@app.context_processor
def inject():
    return {"logged_in": session.get("admin", False)}

@app.route("/")
def announcements():
    with engine.connect() as con:
        rows = con.execute(text("SELECT * FROM announcements ORDER BY pinned DESC, id DESC")).mappings().all()
    return render_template("announcements.html", announcements=rows)

@app.route("/members")
def members():
    with engine.connect() as con:
        rows = con.execute(text("SELECT * FROM members ORDER BY id")).mappings().all()
    return render_template("members.html", members=rows)

@app.route("/rules")
def rules(): return render_template("rules.html")

@app.route("/cards-ranks")
def cards(): return render_template("cards.html")

@app.route("/about-us")
def about(): return render_template("about.html")

@app.route("/oath")
def oath(): return render_template("oath.html")

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        password = request.form.get("password", "")
        stored = os.environ.get("ADMIN_PASSWORD_HASH", "")
        if stored and check_password_hash(stored, password):
            session["admin"] = True
            return redirect(url_for("admin"))
        flash("Incorrect password or admin password is not configured.")
    if not session.get("admin"):
        return render_template("login.html")
    with engine.connect() as con:
        announcements = con.execute(text("SELECT * FROM announcements ORDER BY id DESC")).mappings().all()
        members = con.execute(text("SELECT * FROM members ORDER BY id")).mappings().all()
    return render_template("admin.html", announcements=announcements, members=members)

@app.post("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("announcements"))

@app.post("/admin/announcement/add")
def add_announcement():
    if not session.get("admin"): return redirect(url_for("admin"))
    with engine.begin() as con:
        con.execute(text("""INSERT INTO announcements(title,body,created_at,pinned)
                            VALUES(:title,:body,:created_at,:pinned)"""), {
            "title": request.form["title"], "body": request.form["body"],
            "created_at": datetime.now().strftime("%d %b %Y, %I:%M %p"),
            "pinned": 1 if "pinned" in request.form else 0})
    return redirect(url_for("admin"))

@app.post("/admin/announcement/delete/<int:item_id>")
def delete_announcement(item_id):
    if not session.get("admin"): return redirect(url_for("admin"))
    with engine.begin() as con:
        con.execute(text("DELETE FROM announcements WHERE id=:id"), {"id": item_id})
    return redirect(url_for("admin"))

@app.post("/admin/member/add")
def add_member():
    if not session.get("admin"): return redirect(url_for("admin"))
    with engine.begin() as con:
        con.execute(text("""INSERT INTO members(name,role,code,special_name)
                            VALUES(:name,:role,:code,:special_name)"""), {
            "name": request.form["name"], "role": request.form["role"],
            "code": request.form.get("code",""),
            "special_name": request.form.get("special_name","")})
    return redirect(url_for("admin"))

@app.post("/admin/member/delete/<int:item_id>")
def delete_member(item_id):
    if not session.get("admin"): return redirect(url_for("admin"))
    with engine.begin() as con:
        con.execute(text("DELETE FROM members WHERE id=:id"), {"id": item_id})
    return redirect(url_for("admin"))

init_db()
if __name__ == "__main__":
    app.run(debug=True)
