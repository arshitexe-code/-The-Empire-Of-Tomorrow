# The Empire of Tomorrow

A colorful multi-page Flask website with a private admin dashboard.

## Run locally

1. Install Python 3.10+.
2. In this folder run:
   `pip install -r requirements.txt`
3. Generate an admin password hash:
   `python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('YOUR_PASSWORD'))"`
4. Set environment variables:
   - `ADMIN_PASSWORD_HASH` = the generated hash
   - `SECRET_KEY` = a long random secret
5. Run:
   `python app.py`
6. Open http://127.0.0.1:5000

The public site is multi-page. The admin dashboard at `/admin` is protected by a password and can publish/delete announcements and add/delete members.

For public internet deployment, use a production WSGI server (for example gunicorn) and set strong environment variables. Do not put your password or secret key directly into the source code.
