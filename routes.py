from flask import Flask, render_template, redirect, url_for, session, request
from authlib.integrations.flask_client import OAuth
from config import SessionLocal, AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET, AUTH0_CALLBACK_URL, AUTH0_LOGOUT_REDIRECT
from models import User

app = Flask(__name__)
app.secret_key = "your_secret_key"

# 🔹 Configure Auth0 OAuth
oauth = OAuth(app)
auth0 = oauth.register(
    "auth0",
    client_id=AUTH0_CLIENT_ID,
    client_secret=AUTH0_CLIENT_SECRET,
    api_base_url=f"https://{AUTH0_DOMAIN}",
    access_token_url=f"https://{AUTH0_DOMAIN}/oauth/token",
    authorize_url=f"https://{AUTH0_DOMAIN}/authorize",
    client_kwargs={"scope": "openid profile email"},
    server_metadata_url=f"https://{AUTH0_DOMAIN}/.well-known/openid-configuration",
)

# 🔹 Home Route
@app.route("/")
def index():
    return render_template("index.html")

# 🔹 Auth0 Login Route
@app.route("/login")
def login():
    return auth0.authorize_redirect(redirect_uri=AUTH0_CALLBACK_URL)

# 🔹 Auth0 Callback (Handles User Authentication)
@app.route("/callback")
def callback():
    auth0.authorize_access_token()
    user_info = auth0.get("userinfo").json()
    session["user"] = user_info

    # 🔹 Check if user exists in database
    db_session = SessionLocal()
    existing_user = db_session.query(User).filter_by(auth0_id=user_info["sub"]).first()
    if not existing_user:
        new_user = User(
            auth0_id=user_info["sub"],
            name=user_info["name"],
            email=user_info["email"],
            picture=user_info["picture"],
        )
        db_session.add(new_user)
        db_session.commit()
    db_session.close()

    return redirect(url_for("profile"))

# 🔹 Profile Page
@app.route("/profile")
def profile():
    user_info = session.get("user")
    if not user_info:
        return redirect(url_for("login"))
    return render_template("profile.html", user=user_info)

# 🔹 Logout Route
@app.route("/logout")
def logout():
    session.clear()
    return redirect(
        f"https://{AUTH0_DOMAIN}/v2/logout?"
        f"client_id={AUTH0_CLIENT_ID}&"
        f"returnTo={AUTH0_LOGOUT_REDIRECT}"
    )
