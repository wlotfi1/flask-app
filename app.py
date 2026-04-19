import os
from datetime import datetime, timedelta
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, abort
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "rbxstore-super-secret-key-change-me"

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'store.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "static", "uploads")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "ico"}
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "rbxstore123"
DEFAULT_DISCORD_ID = "YOUR_DISCORD_ID"

db = SQLAlchemy(app)


class SiteConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    site_name = db.Column(db.String(100), default="RbxStore")
    favicon_filename = db.Column(db.String(300), nullable=True)

    @property
    def favicon_url(self):
        if self.favicon_filename:
            return url_for("static", filename=f"uploads/{self.favicon_filename}")
        return None


class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    image_filename = db.Column(db.String(300), nullable=True)
    discord_link = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_new(self):
        return datetime.utcnow() - self.created_at < timedelta(days=3)

    @property
    def image_url(self):
        if self.image_filename:
            return url_for("static", filename=f"uploads/{self.image_filename}")
        return "https://placehold.co/400x300/2b2b36/aaaaaa?text=No+Image"

    @property
    def contact_url(self):
        if self.discord_link:
            return self.discord_link
        return f"https://discord.com/users/{DEFAULT_DISCORD_ID}"


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash("Please log in to access the admin panel.", "warning")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


@app.context_processor
def inject_now():
    config = SiteConfig.query.first()
    return {
        "now": datetime.utcnow(),
        "site_config": config
    }


# --- Public Routes ---

@app.route("/")
def index():
    featured = Listing.query.order_by(Listing.created_at.desc()).limit(6).all()
    return render_template("index.html", featured=featured)


@app.route("/items")
def items():
    q = request.args.get("q", "").strip()
    query = Listing.query.filter_by(category="items")
    if q:
        query = query.filter(Listing.title.ilike(f"%{q}%"))
    listings = query.order_by(Listing.created_at.desc()).all()
    return render_template("category.html", listings=listings, category="Items", q=q)


@app.route("/robux")
def robux():
    q = request.args.get("q", "").strip()
    query = Listing.query.filter_by(category="robux")
    if q:
        query = query.filter(Listing.title.ilike(f"%{q}%"))
    listings = query.order_by(Listing.created_at.desc()).all()
    return render_template("category.html", listings=listings, category="Robux", q=q)


@app.route("/accounts")
def accounts():
    q = request.args.get("q", "").strip()
    query = Listing.query.filter_by(category="accounts")
    if q:
        query = query.filter(Listing.title.ilike(f"%{q}%"))
    listings = query.order_by(Listing.created_at.desc()).all()
    return render_template("category.html", listings=listings, category="Accounts", q=q)


@app.route("/listing/<int:listing_id>")
def listing_detail(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    return render_template("listing.html", listing=listing)


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return redirect(url_for("index"))
    listings = Listing.query.filter(Listing.title.ilike(f"%{q}%")).order_by(Listing.created_at.desc()).all()
    return render_template("category.html", listings=listings, category=f'Search: "{q}"', q=q)


# --- Admin Routes ---

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("username") == ADMIN_USERNAME and request.form.get("password") == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            flash("Welcome back, admin!", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Invalid credentials.", "danger")
    return render_template("admin/login.html")


@app.route("/admin/settings", methods=["GET", "POST"])
@login_required
def admin_settings():
    config = SiteConfig.query.first()
    if not config:
        config = SiteConfig(site_name="RbxStore")
        db.session.add(config)
        db.session.commit()

    if request.method == "POST":
        config.site_name = request.form.get("site_name", "RbxStore").strip()
        file = request.files.get("favicon")
        if file and file.filename and allowed_file(file.filename):
            if config.favicon_filename:
                old = os.path.join(app.config["UPLOAD_FOLDER"], config.favicon_filename)
                if os.path.exists(old):
                    try:
                        os.remove(old)
                    except Exception:
                        pass
            config.favicon_filename = secure_filename(f"fav_{int(datetime.utcnow().timestamp())}_{file.filename}")
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], config.favicon_filename))
        
        db.session.commit()
        flash("Settings updated successfully!", "success")
        return redirect(url_for("admin_settings"))
        
    return render_template("admin/settings.html", config=config)


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    flash("Logged out successfully.", "info")
    return redirect(url_for("index"))


@app.route("/admin")
@login_required
def admin_dashboard():
    listings = Listing.query.order_by(Listing.created_at.desc()).all()
    stats = {
        "total": len(listings),
        "items": sum(1 for l in listings if l.category == "items"),
        "robux": sum(1 for l in listings if l.category == "robux"),
        "accounts": sum(1 for l in listings if l.category == "accounts"),
    }
    return render_template("admin/dashboard.html", listings=listings, stats=stats)


@app.route("/admin/add", methods=["GET", "POST"])
@login_required
def admin_add():
    if request.method == "POST":
        image_filename = None
        file = request.files.get("image")
        if file and file.filename and allowed_file(file.filename):
            image_filename = secure_filename(f"{int(datetime.utcnow().timestamp())}_{file.filename}")
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], image_filename))

        listing = Listing(
            title=request.form["title"],
            description=request.form["description"],
            price=float(request.form["price"]),
            category=request.form["category"],
            image_filename=image_filename,
            discord_link=request.form.get("discord_link", "").strip() or None,
        )
        db.session.add(listing)
        db.session.commit()
        flash("Listing added successfully!", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/add.html")


@app.route("/admin/edit/<int:listing_id>", methods=["GET", "POST"])
@login_required
def admin_edit(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    if request.method == "POST":
        listing.title = request.form["title"]
        listing.description = request.form["description"]
        listing.price = float(request.form["price"])
        listing.category = request.form["category"]
        listing.discord_link = request.form.get("discord_link", "").strip() or None

        file = request.files.get("image")
        if file and file.filename and allowed_file(file.filename):
            if listing.image_filename:
                old = os.path.join(app.config["UPLOAD_FOLDER"], listing.image_filename)
                if os.path.exists(old):
                    os.remove(old)
            listing.image_filename = secure_filename(f"{int(datetime.utcnow().timestamp())}_{file.filename}")
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], listing.image_filename))

        db.session.commit()
        flash("Listing updated successfully!", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/edit.html", listing=listing)


@app.route("/admin/delete/<int:listing_id>", methods=["POST"])
@login_required
def admin_delete(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    if listing.image_filename:
        p = os.path.join(app.config["UPLOAD_FOLDER"], listing.image_filename)
        if os.path.exists(p):
            os.remove(p)
    db.session.delete(listing)
    db.session.commit()
    flash("Listing deleted.", "info")
    return redirect(url_for("admin_dashboard"))


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    with app.app_context():
        db.create_all()
        if not SiteConfig.query.first():
            db.session.add(SiteConfig(site_name="RbxStore"))
            db.session.commit()
    app.run(debug=True, port=5000)
