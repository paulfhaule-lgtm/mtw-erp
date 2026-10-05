import os, csv, io
from datetime import date, datetime, timedelta
from decimal import Decimal
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func, extract

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-in-production")
database_url = os.getenv("DATABASE_URL", "sqlite:///mtw_accounts.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(40), default="Accounts Officer")

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    txn_date = db.Column(db.Date, nullable=False, default=date.today)
    txn_type = db.Column(db.String(20), nullable=False)  # Income / Expense
    category = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(14,2), nullable=False)
    payment_method = db.Column(db.String(40), default="Cash")
    reference = db.Column(db.String(100))
    project = db.Column(db.String(120))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

CATEGORIES = [
    "Sales/Income", "Client Payment", "Other Income",
    "Materials", "Transport", "Fundi/Labour", "Salary", "Weekly Pay",
    "Electricity", "Water", "Rent", "PAYE", "NSSF", "WCF", "SDL",
    "VAT", "Corporate Tax", "Office Furniture/Equipment", "Fuel",
    "Repairs/Maintenance", "Bank Charges", "Internet", "Other Expense"
]

@app.before_request
def setup():
    if request.endpoint in {"login", "static", "health"}:
        return
    if "user_id" not in session:
        return redirect(url_for("login"))

@app.route("/health")
def health():
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify(status="ok", database="connected")
    except Exception as e:
        return jsonify(status="error", database="disconnected", error=str(e)), 503

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            return redirect(url_for("dashboard"))
        flash("Username au password si sahihi.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

def period_dates(period):
    today = date.today()
    if period == "day":
        return today, today
    if period == "week":
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)
    if period == "month":
        start = today.replace(day=1)
        if start.month == 12:
            nxt = date(start.year+1,1,1)
        else:
            nxt = date(start.year,start.month+1,1)
        return start, nxt - timedelta(days=1)
    return date(today.year,1,1), date(today.year,12,31)

def totals(start, end):
    income = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.txn_type=="Income", Transaction.txn_date.between(start,end)).scalar()
    expense = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.txn_type=="Expense", Transaction.txn_date.between(start,end)).scalar()
    return Decimal(str(income or 0)), Decimal(str(expense or 0))

@app.route("/")
def dashboard():
    today = date.today()
    cards = {}
    for p in ["day","week","month","year"]:
        s,e = period_dates(p)
        inc, exp = totals(s,e)
        cards[p] = {"start":s, "end":e, "income":inc, "expense":exp, "balance":inc-exp}
    recent = Transaction.query.order_by(Transaction.txn_date.desc(), Transaction.id.desc()).limit(12).all()
    return render_template("dashboard.html", cards=cards, recent=recent)

@app.route("/transactions")
def transactions():
    q = Transaction.query
    txn_type = request.args.get("type")
    category = request.args.get("category")
    start = request.args.get("start")
    end = request.args.get("end")
    if txn_type in ("Income","Expense"):
        q = q.filter_by(txn_type=txn_type)
    if category:
        q = q.filter_by(category=category)
    if start:
        q = q.filter(Transaction.txn_date >= datetime.strptime(start,"%Y-%m-%d").date())
    if end:
        q = q.filter(Transaction.txn_date <= datetime.strptime(end,"%Y-%m-%d").date())
    rows = q.order_by(Transaction.txn_date.desc(), Transaction.id.desc()).all()
    inc = sum((Decimal(str(x.amount)) for x in rows if x.txn_type=="Income"), Decimal("0"))
    exp = sum((Decimal(str(x.amount)) for x in rows if x.txn_type=="Expense"), Decimal("0"))
    return render_template("transactions.html", rows=rows, income=inc, expense=exp, balance=inc-exp, categories=CATEGORIES)

@app.route("/transactions/new", methods=["GET","POST"])
def new_transaction():
    if request.method == "POST":
        try:
            amount = Decimal(request.form["amount"])
            if amount <= 0:
                raise ValueError
            t = Transaction(
                txn_date=datetime.strptime(request.form["txn_date"], "%Y-%m-%d").date(),
                txn_type=request.form["txn_type"],
                category=request.form["category"],
                description=request.form["description"].strip(),
                amount=amount,
                payment_method=request.form.get("payment_method","Cash"),
                reference=request.form.get("reference","").strip(),
                project=request.form.get("project","").strip(),
                notes=request.form.get("notes","").strip()
            )
            db.session.add(t)
            db.session.commit()
            flash("Transaction imehifadhiwa.", "success")
            return redirect(url_for("transactions"))
        except Exception:
            db.session.rollback()
            flash("Tafadhali hakikisha taarifa zote na kiasi ni sahihi.", "danger")
    return render_template("transaction_form.html", categories=CATEGORIES, today=date.today().isoformat())

@app.route("/transactions/<int:txn_id>/delete", methods=["POST"])
def delete_transaction(txn_id):
    t = db.get_or_404(Transaction, txn_id)
    db.session.delete(t)
    db.session.commit()
    flash("Transaction imefutwa.", "success")
    return redirect(url_for("transactions"))

@app.route("/reports")
def reports():
    period = request.args.get("period","month")
    start, end = period_dates(period)
    inc, exp = totals(start,end)
    by_category = db.session.query(
        Transaction.txn_type, Transaction.category, func.sum(Transaction.amount)
    ).filter(Transaction.txn_date.between(start,end)).group_by(
        Transaction.txn_type, Transaction.category
    ).order_by(Transaction.txn_type, Transaction.category).all()
    daily = db.session.query(
        Transaction.txn_date, Transaction.txn_type, func.sum(Transaction.amount)
    ).filter(Transaction.txn_date.between(start,end)).group_by(
        Transaction.txn_date, Transaction.txn_type
    ).order_by(Transaction.txn_date).all()
    return render_template("reports.html", period=period, start=start, end=end,
                           income=inc, expense=exp, balance=inc-exp,
                           by_category=by_category, daily=daily)

@app.route("/export.csv")
def export_csv():
    start = request.args.get("start")
    end = request.args.get("end")
    q = Transaction.query.order_by(Transaction.txn_date, Transaction.id)
    if start: q=q.filter(Transaction.txn_date >= datetime.strptime(start,"%Y-%m-%d").date())
    if end: q=q.filter(Transaction.txn_date <= datetime.strptime(end,"%Y-%m-%d").date())
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Date","Type","Category","Description","Amount","Payment Method","Reference","Project","Notes"])
    for t in q.all():
        writer.writerow([t.txn_date,t.txn_type,t.category,t.description,t.amount,t.payment_method,t.reference,t.project,t.notes])
    mem = io.BytesIO(out.getvalue().encode("utf-8-sig"))
    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name="mtw_accounts_report.csv")

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username="accounts").first():
        pwd = os.getenv("ACCOUNTS_PASSWORD", "ChangeMe123!")
        db.session.add(User(username="accounts", password_hash=generate_password_hash(pwd), role="Accounts Officer"))
        db.session.commit()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
