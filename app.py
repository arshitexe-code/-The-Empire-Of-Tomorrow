import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import check_password_hash
import secrets
from sqlalchemy import create_engine, text

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")
app.permanent_session_lifetime = timedelta(days=30)

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
                secret_code TEXT DEFAULT '', secret_name TEXT DEFAULT '',
                created_at TIMESTAMPTZ DEFAULT NOW())"""))
            con.execute(text("""CREATE TABLE IF NOT EXISTS chat_messages (
                id BIGSERIAL PRIMARY KEY, member_id BIGINT NOT NULL, member_name TEXT NOT NULL,
                message TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW())"""))
        else:
            con.execute(text("""CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, body TEXT NOT NULL,
                created_at TEXT NOT NULL, pinned INTEGER DEFAULT 0)"""))
            con.execute(text("""CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, role TEXT NOT NULL,
                secret_code TEXT DEFAULT '', secret_name TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP)"""))
            con.execute(text("""CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, member_id INTEGER NOT NULL, member_name TEXT NOT NULL,
                message TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)"""))

@app.context_processor
def inject():
    return {
        "logged_in": session.get("admin", False),
        "member_logged_in": bool(session.get("member_id")),
        "member_name": session.get("member_name", ""),
        "site_last_updated": os.environ.get("SITE_LAST_UPDATED", "05 Oct 2026")
    }

@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404

@app.route("/")
def announcements():
    with engine.connect() as con:
        rows = con.execute(text("SELECT * FROM announcements ORDER BY pinned DESC, id DESC")).mappings().all()
        member_count = con.execute(text("SELECT COUNT(*) FROM members")).scalar_one()
        leadership = con.execute(text("SELECT name, role FROM members WHERE lower(role) IN ('Group Leader') ORDER BY id")).mappings().all()
    return render_template("announcements.html", announcements=rows, member_count=member_count, leadership=leadership)

@app.route("/dashboard")
def dashboard():
    if not session.get("member_id"):
        return redirect(url_for("chat"))
    return render_template("dashboard.html")

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

@app.route("/chat", methods=["GET", "POST"])
def chat():
    # The login popup is part of the chat page itself. A successful login
    # creates a persistent Flask session for this browser for up to 30 days.
    if request.method == "POST":
        name = request.form.get("member_name", "").strip()
        secret_name = request.form.get("secret_name", "").strip()
        secret_code = request.form.get("secret_code", "").strip()
        password = request.form.get("password", "")
        shared_password = os.environ.get("MEMBER_CHAT_PASSWORD", "")

        if not shared_password:
            return render_template("chat.html", messages=[], login_error="Member chat password is not configured yet.", show_login=True)

        with engine.connect() as con:
            member = con.execute(text("""SELECT id, name, secret_name, secret_code
                                        FROM members
                                        WHERE lower(name)=lower(:name)
                                          AND lower(secret_name)=lower(:secret_name)
                                          AND secret_code=:secret_code
                                        LIMIT 1"""), {
                "name": name, "secret_name": secret_name, "secret_code": secret_code
            }).mappings().first()

        if member and secrets.compare_digest(password, shared_password):
            session.permanent = True
            session["member_id"] = member["id"]
            session["member_name"] = member["name"]
            return redirect(url_for("chat"))

        return render_template("chat.html", messages=[], login_error="The member details or shared password are incorrect.", show_login=True)

    # Validate the remembered member still exists.
    member_id = session.get("member_id")
    if member_id:
        with engine.connect() as con:
            member = con.execute(text("SELECT id, name FROM members WHERE id=:id"), {"id": member_id}).mappings().first()
        if not member:
            session.pop("member_id", None)
            session.pop("member_name", None)

    if not session.get("member_id"):
        return render_template("chat.html", messages=[], show_login=True)

    with engine.connect() as con:
        messages = con.execute(text("""SELECT id, member_id, member_name, message, created_at
                                      FROM chat_messages ORDER BY id DESC LIMIT 100""")).mappings().all()
    messages = list(reversed(messages))
    return render_template("chat.html", messages=messages, show_login=False)

@app.post("/chat/logout")
def member_logout():
    session.pop("member_id", None)
    session.pop("member_name", None)
    return redirect(url_for("chat"))

@app.get("/chat/messages")
def chat_messages():
    if not session.get("member_id"):
        return jsonify({"error": "Not authenticated"}), 401
    with engine.connect() as con:
        messages = con.execute(text("""SELECT id, member_id, member_name, message, created_at
                                      FROM chat_messages ORDER BY id DESC LIMIT 100""")).mappings().all()
    return jsonify({"messages": list(reversed([dict(m) for m in messages]))})

@app.post("/chat/send")
def chat_send():
    if not session.get("member_id"):
        return jsonify({"error": "Not authenticated"}), 401
    message = request.form.get("message", "").strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400
    if len(message) > 2000:
        return jsonify({"error": "Message is too long"}), 400
    with engine.begin() as con:
        con.execute(text("""INSERT INTO chat_messages(member_id, member_name, message)
                            VALUES(:member_id, :member_name, :message)"""), {
            "member_id": session["member_id"],
            "member_name": session.get("member_name", "Member"),
            "message": message
        })
    return jsonify({"ok": True})

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
        chat_messages = con.execute(text("SELECT * FROM chat_messages ORDER BY id DESC LIMIT 100")).mappings().all()
    return render_template("admin.html", announcements=announcements, members=members, chat_messages=chat_messages)

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
        con.execute(text("""INSERT INTO members(name,role,secret_code,secret_name)
                            VALUES(:name,:role,:secret_code,:secret_name)"""), {
            "name": request.form["name"], "role": request.form["role"],
            "secret_code": request.form.get("secret_code",""),
            "secret_name": request.form.get("secret_name","")})
    return redirect(url_for("admin"))

@app.post("/admin/member/delete/<int:item_id>")
def delete_member(item_id):
    if not session.get("admin"): return redirect(url_for("admin"))
    with engine.begin() as con:
        con.execute(text("DELETE FROM members WHERE id=:id"), {"id": item_id})
    return redirect(url_for("admin"))

@app.post("/admin/chat/delete/<int:item_id>")
def delete_chat_message(item_id):
    if not session.get("admin"): return redirect(url_for("admin"))
    with engine.begin() as con:
        con.execute(text("DELETE FROM chat_messages WHERE id=:id"), {"id": item_id})
    return redirect(url_for("admin"))

init_db()
if __name__ == "__main__":
    app.run(debug=True)
