from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
DB = "empire.db"
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH")

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.execute("""CREATE TABLE IF NOT EXISTS announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        created_at TEXT NOT NULL,
        pinned INTEGER DEFAULT 0
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        code TEXT DEFAULT '',
        special_name TEXT DEFAULT ''
    )""")
    con.commit()
    con.close()

@app.context_processor
def inject():
    return {"logged_in": session.get("admin", False)}

@app.route("/")
def announcements():
    con = db()
    rows = con.execute("SELECT * FROM announcements ORDER BY pinned DESC, id DESC").fetchall()
    con.close()
    return render_template("announcements.html", announcements=rows)

@app.route("/members")
def members():
    con = db()
    rows = con.execute("SELECT * FROM members ORDER BY id").fetchall()
    con.close()
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
        if not ADMIN_PASSWORD_HASH:
            flash("Set ADMIN_PASSWORD_HASH before using the admin login.", "error")
        elif check_password_hash(ADMIN_PASSWORD_HASH, password):
            session["admin"] = True
            return redirect(url_for("admin"))
        else:
            flash("Incorrect password.", "error")
    if not session.get("admin"):
        return render_template("login.html")
    con = db()
    announcements = con.execute("SELECT * FROM announcements ORDER BY id DESC").fetchall()
    members = con.execute("SELECT * FROM members ORDER BY id").fetchall()
    con.close()
    return render_template("admin.html", announcements=announcements, members=members)

@app.post("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("announcements"))

@app.post("/admin/announcement/add")
def add_announcement():
    if not session.get("admin"): return redirect(url_for("admin"))
    con = db()
    con.execute("INSERT INTO announcements(title, body, created_at, pinned) VALUES(?,?,?,?)",
                (request.form["title"], request.form["body"], datetime.now().strftime("%d %b %Y, %I:%M %p"), int("pinned" in request.form)))
    con.commit(); con.close()
    return redirect(url_for("admin"))

@app.post("/admin/announcement/delete/<int:item_id>")
def delete_announcement(item_id):
    if not session.get("admin"): return redirect(url_for("admin"))
    con = db(); con.execute("DELETE FROM announcements WHERE id=?", (item_id,)); con.commit(); con.close()
    return redirect(url_for("admin"))

@app.post("/admin/member/add")
def add_member():
    if not session.get("admin"): return redirect(url_for("admin"))
    con = db()
    con.execute("INSERT INTO members(name, role, code, special_name) VALUES(?,?,?,?)",
                (request.form["name"], request.form["role"], request.form.get("code",""), request.form.get("special_name","")))
    con.commit(); con.close()
    return redirect(url_for("admin"))

@app.post("/admin/member/delete/<int:item_id>")
def delete_member(item_id):
    if not session.get("admin"): return redirect(url_for("admin"))
    con = db(); con.execute("DELETE FROM members WHERE id=?", (item_id,)); con.commit(); con.close()
    return redirect(url_for("admin"))

init_db()
if __name__ == "__main__":
    app.run(debug=True)
