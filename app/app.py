
import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "1").lower() in {"1", "true", "yes"}
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_UPLOAD_MB", "16")) * 1024 * 1024
db_url = os.environ.get("DATABASE_URL", "sqlite:///mtw_erp.db")
if db_url.startswith("postgres://"): db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_DIR"] = os.environ.get("UPLOAD_DIR", "/data/mtw_uploads")
os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)
ALLOWED_UPLOADS = {"png", "jpg", "jpeg", "webp", "gif"}
db = SQLAlchemy(app)

USERS = {
    "accounts": ("Accounts + Sales/Reception", os.environ.get("ACCOUNTS_PASSWORD", "accounts123")),
    "production": ("Production Director + Production", os.environ.get("PRODUCTION_PASSWORD", "production123")),
    "store": ("Store Keeper + Procurement", os.environ.get("STORE_PASSWORD", "store123")),
    "md": ("Managing Director", os.environ.get("MD_PASSWORD", "md123")),
}
ROLE_NAME = {k:v[0] for k,v in USERS.items()}

class User(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    username=db.Column(db.String(80), unique=True, nullable=False)
    password_hash=db.Column(db.String(255), nullable=False)
    role=db.Column(db.String(120), nullable=False)
    active=db.Column(db.Boolean, default=True)

class Project(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    code=db.Column(db.String(40), unique=True, nullable=False)
    name=db.Column(db.String(200), nullable=False)
    client=db.Column(db.String(200), nullable=False)
    contract_amount=db.Column(db.Float, default=0)
    status=db.Column(db.String(40), default="Active")
    created_at=db.Column(db.DateTime, default=datetime.utcnow)

class Document(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    doc_no=db.Column(db.String(60), unique=True)
    project=db.Column(db.String(200))
    stage=db.Column(db.String(100))
    holder=db.Column(db.String(100))
    status=db.Column(db.String(40), default="Pending Action")
    priority=db.Column(db.String(20), default="Normal")
    comments=db.Column(db.Text)
    created_by=db.Column(db.String(80))
    created_at=db.Column(db.DateTime, default=datetime.utcnow)
    updated_at=db.Column(db.DateTime, default=datetime.utcnow)

class Audit(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    doc_no=db.Column(db.String(60))
    action=db.Column(db.String(255))
    by_user=db.Column(db.String(80))
    routed_to=db.Column(db.String(100))
    created_at=db.Column(db.DateTime, default=datetime.utcnow)

class Inventory(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    sku=db.Column(db.String(60), unique=True)
    item=db.Column(db.String(200), nullable=False)
    unit=db.Column(db.String(30), default="pcs")
    qty=db.Column(db.Float, default=0)
    reorder_level=db.Column(db.Float, default=0)

class Invoice(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    invoice_no=db.Column(db.String(60), unique=True)
    client=db.Column(db.String(200))
    project=db.Column(db.String(200))
    amount=db.Column(db.Float, default=0)
    paid=db.Column(db.Float, default=0)
    status=db.Column(db.String(40), default="Unpaid")
    created_at=db.Column(db.DateTime, default=datetime.utcnow)

class MaterialRequest(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    request_no=db.Column(db.String(60), unique=True, nullable=False)
    project_id=db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    request_type=db.Column(db.String(30), default="Original")
    parent_id=db.Column(db.Integer, db.ForeignKey("material_request.id"))
    requested_by=db.Column(db.String(80))
    status=db.Column(db.String(40), default="Draft")
    reason=db.Column(db.Text)
    created_at=db.Column(db.DateTime, default=datetime.utcnow)
    updated_at=db.Column(db.DateTime, default=datetime.utcnow)
    project=db.relationship("Project", backref="material_requests")
    items=db.relationship("MaterialRequestItem", backref="request", cascade="all, delete-orphan")

class MaterialRequestItem(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    request_id=db.Column(db.Integer, db.ForeignKey("material_request.id"), nullable=False)
    item=db.Column(db.String(200), nullable=False)
    specification=db.Column(db.String(200))
    quantity=db.Column(db.Float, default=0)
    unit=db.Column(db.String(30), default="pcs")
    reason=db.Column(db.Text)

class PaymentRequest(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    request_no=db.Column(db.String(60), unique=True, nullable=False)
    project_id=db.Column(db.Integer, db.ForeignKey("project.id"))
    requested_by=db.Column(db.String(80))
    department=db.Column(db.String(100))
    payee=db.Column(db.String(200))
    payment_type=db.Column(db.String(100))
    description=db.Column(db.Text)
    amount_requested=db.Column(db.Float, default=0)
    amount_approved=db.Column(db.Float, default=0)
    amount_paid=db.Column(db.Float, default=0)
    due_date=db.Column(db.String(30))
    payment_method=db.Column(db.String(40))
    status=db.Column(db.String(40), default="Draft")
    notes=db.Column(db.Text)
    created_at=db.Column(db.DateTime, default=datetime.utcnow)
    project=db.relationship("Project", backref="payment_requests")

class Payment(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    payment_no=db.Column(db.String(60), unique=True, nullable=False)
    payment_request_id=db.Column(db.Integer, db.ForeignKey("payment_request.id"))
    payee=db.Column(db.String(200))
    project_id=db.Column(db.Integer, db.ForeignKey("project.id"))
    amount=db.Column(db.Float, default=0)
    method=db.Column(db.String(40))
    reference=db.Column(db.String(120))
    notes=db.Column(db.Text)
    paid_by=db.Column(db.String(80))
    created_at=db.Column(db.DateTime, default=datetime.utcnow)
    request=db.relationship("PaymentRequest", backref="payments")
    project=db.relationship("Project")

class Loan(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    loan_no=db.Column(db.String(60), unique=True, nullable=False)
    project_id=db.Column(db.Integer, db.ForeignKey("project.id"))
    person=db.Column(db.String(200), nullable=False)
    person_type=db.Column(db.String(30), default="Fundi")
    amount_requested=db.Column(db.Float, default=0)
    amount_issued=db.Column(db.Float, default=0)
    status=db.Column(db.String(40), default="Requested")
    reason=db.Column(db.Text)
    requested_by=db.Column(db.String(80))
    created_at=db.Column(db.DateTime, default=datetime.utcnow)
    project=db.relationship("Project", backref="loans")
    repayments=db.relationship("LoanRepayment", backref="loan", cascade="all, delete-orphan")
    @property
    def repaid(self): return sum(x.amount or 0 for x in self.repayments)
    @property
    def balance(self): return max((self.amount_issued or 0)-self.repaid, 0)

class LoanRepayment(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    loan_id=db.Column(db.Integer, db.ForeignKey("loan.id"), nullable=False)
    amount=db.Column(db.Float, default=0)
    method=db.Column(db.String(40))
    reference=db.Column(db.String(120))
    paid_by=db.Column(db.String(80))
    created_at=db.Column(db.DateTime, default=datetime.utcnow)

class ProjectFundi(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    project_id=db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    name=db.Column(db.String(200), nullable=False)
    role=db.Column(db.String(100))
    agreed_labour=db.Column(db.Float, default=0)
    status=db.Column(db.String(40), default="Active")
    created_at=db.Column(db.DateTime, default=datetime.utcnow)
    project=db.relationship("Project", backref="fundis")
    payments=db.relationship("LabourPayment", backref="fundi", cascade="all, delete-orphan")
    @property
    def total_paid(self): return sum(x.amount or 0 for x in self.payments)
    @property
    def balance(self): return max((self.agreed_labour or 0)-self.total_paid, 0)

class LabourPayment(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    fundi_id=db.Column(db.Integer, db.ForeignKey("project_fundi.id"), nullable=False)
    amount=db.Column(db.Float, default=0)
    method=db.Column(db.String(40))
    reference=db.Column(db.String(120))
    paid_by=db.Column(db.String(80))
    notes=db.Column(db.Text)
    created_at=db.Column(db.DateTime, default=datetime.utcnow)

STAGES=[
 ("Customer Order","accounts"),("Job Card","production"),("Material Request","production"),
 ("Stock Check","store"),("Material Issue","production"),("Purchase Request","store"),
 ("Quotation / Supplier","store"),("MD Approval","md"),("Purchase Order","store"),
 ("Delivery","store"),("GRN","store"),("Supplier Invoice","accounts"),("3-Way Check","accounts"),
 ("Payment Voucher","accounts"),("MD Payment Approval","md"),("Payment","accounts"),
 ("Proof of Payment","accounts"),("Accounting + Stock + Supplier Record","accounts")
]

def current_user(): return session.get("username")
def role(): return session.get("username")
def login_required(f):
    @wraps(f)
    def w(*a,**kw):
        if not current_user(): return redirect(url_for("login"))
        return f(*a,**kw)
    return w
def roles_required(*allowed):
    def deco(f):
        @wraps(f)
        def w(*a,**kw):
            if not current_user(): return redirect(url_for("login"))
            if current_user() not in allowed:
                flash("Huna ruhusa ya kufanya action hii.", "error")
                return redirect(request.referrer or url_for("dashboard"))
            return f(*a,**kw)
        return w
    return deco
def audit(doc, action, routed="-"):
    db.session.add(Audit(doc_no=doc, action=action, by_user=current_user(), routed_to=routed))
def next_no(prefix, model):
    return f"{prefix}-{model.query.count()+1:06d}"

@app.context_processor
def inject_globals():
    cfg={x.key:x.value for x in Setting.query.all()} if 'Setting' in globals() else {}
    logo=f"/uploads/{cfg['logo_path']}" if cfg.get('logo_path') else ""
    return {"role_name": ROLE_NAME.get(current_user(), ""), "now": datetime.utcnow(), "company_name": cfg.get('company_name','MTW ERP'), "company_logo": logo, "company_stamp": (f"/uploads/{cfg['stamp_path']}" if cfg.get('stamp_path') else "")}

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=request.form["username"].strip().lower(); p=request.form["password"]
        user=User.query.filter_by(username=u, active=True).first()
        if user and check_password_hash(user.password_hash,p):
            session["username"]=u
            return redirect(url_for("dashboard"))
        flash("Invalid username or password","error")
    return render_template("login.html")

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("login"))

@app.route("/")
@login_required
def dashboard():
    projects=Project.query.order_by(Project.id.desc()).all()
    docs=Document.query.order_by(Document.updated_at.desc()).limit(12).all()
    invoices=Invoice.query.all()
    contract=sum(p.contract_amount or 0 for p in projects)
    billed=sum(i.amount or 0 for i in invoices); paid=sum(i.paid or 0 for i in invoices)
    return render_template("dashboard.html", user=current_user(), projects=projects, docs=docs,
        contract=contract,billed=billed,paid=paid,debt=billed-paid,
        material_pending=MaterialRequest.query.filter(MaterialRequest.status.in_(["Submitted","Returned"])).count(),
        payment_pending=PaymentRequest.query.filter(PaymentRequest.status.in_(["Submitted","Under Review"])).count())

@app.route("/projects", methods=["GET","POST"])
@login_required
def projects():
    if request.method=="POST":
        p=Project(code=request.form["code"].strip(),name=request.form["name"].strip(),client=request.form["client"].strip(),
                  contract_amount=float(request.form.get("contract_amount") or 0))
        db.session.add(p); db.session.commit(); flash("Project created","ok"); return redirect(url_for("projects"))
    return render_template("projects.html",projects=Project.query.order_by(Project.id.desc()).all())

@app.route("/projects/<int:pid>")
@login_required
def project_detail(pid):
    p=Project.query.get_or_404(pid)
    return render_template("project_detail.html", p=p,
        materials=MaterialRequest.query.filter_by(project_id=pid).order_by(MaterialRequest.id.desc()).all(),
        payments=PaymentRequest.query.filter_by(project_id=pid).order_by(PaymentRequest.id.desc()).all(),
        loans=Loan.query.filter_by(project_id=pid).order_by(Loan.id.desc()).all())

@app.route("/documents",methods=["GET"])
@login_required
def documents():
    return render_template("documents.html",docs=Document.query.order_by(Document.updated_at.desc()).all(), stages=STAGES)

@app.route("/documents/new",methods=["POST"])
@login_required
def new_document():
    no=request.form.get("doc_no") or next_no("WO",Document)
    d=Document(doc_no=no,project=request.form.get("project",""),stage="Customer Order",holder="accounts",created_by=current_user())
    db.session.add(d); db.session.flush(); audit(no,"Created / Customer Order","accounts"); db.session.commit()
    flash("Workflow started","ok"); return redirect(url_for("documents"))

def route_after(stage, stock_available=None):
    names=[s for s,r in STAGES]
    try:i=names.index(stage)
    except ValueError:return None
    if stage=="Stock Check": return ("Material Issue","production") if stock_available else ("Purchase Request","store")
    return STAGES[i+1] if i+1<len(STAGES) else None

@app.route("/documents/<int:id>/complete",methods=["POST"])
@login_required
def complete(id):
    d=Document.query.get_or_404(id)
    if d.holder!=current_user(): flash("You are not the current holder","error"); return redirect(url_for("documents"))
    stock=request.form.get("stock_available")=="yes" if d.stage=="Stock Check" else None
    nxt=route_after(d.stage,stock); old=d.stage
    if nxt:
        d.stage,d.holder=nxt; d.status="Pending Action"; audit(d.doc_no,f"Completed {old}; routed to {d.stage}",d.holder)
    else:
        d.status="Completed"; audit(d.doc_no,"Workflow completed","-")
    d.updated_at=datetime.utcnow(); db.session.commit(); return redirect(url_for("documents"))

@app.route("/inventory",methods=["GET","POST"])
@login_required
def inventory():
    if request.method=="POST":
        sku=request.form.get("sku","").strip() or next_no("SKU",Inventory)
        item=Inventory.query.filter_by(sku=sku).first()
        if not item:
            item=Inventory(sku=sku,item=request.form["item"],unit=request.form.get("unit","pcs"),qty=float(request.form.get("qty") or 0),reorder_level=float(request.form.get("reorder") or 0)); db.session.add(item)
        else: item.qty += float(request.form.get("qty") or 0)
        db.session.commit(); return redirect(url_for("inventory"))
    return render_template("inventory.html",items=Inventory.query.order_by(Inventory.item).all())

@app.route("/invoices",methods=["GET","POST"])
@login_required
def invoices():
    if request.method=="POST":
        inv=Invoice(invoice_no=request.form.get("invoice_no") or next_no("INV",Invoice),client=request.form["client"],
                    project=request.form.get("project",""),amount=float(request.form.get("amount") or 0))
        db.session.add(inv); db.session.commit(); return redirect(url_for("invoices"))
    return render_template("invoices.html",invoices=Invoice.query.order_by(Invoice.id.desc()).all())

# ---- Material Requests: free text materials + additional requests ----
@app.route("/materials",methods=["GET","POST"])
@login_required
def materials():
    projects=Project.query.order_by(Project.name).all()
    if request.method=="POST":
        pid=int(request.form["project_id"]); p=Project.query.get_or_404(pid)
        req=MaterialRequest(request_no=next_no("MR",MaterialRequest),project_id=pid,request_type=request.form.get("request_type","Original"),
                            requested_by=current_user(),reason=request.form.get("reason",""),status="Submitted")
        db.session.add(req); db.session.flush()
        items=request.form.getlist("item[]"); specs=request.form.getlist("specification[]"); qtys=request.form.getlist("quantity[]"); units=request.form.getlist("unit[]"); reasons=request.form.getlist("item_reason[]")
        for i,name in enumerate(items):
            if name.strip():
                req.items.append(MaterialRequestItem(item=name.strip(), specification=specs[i] if i<len(specs) else "", quantity=float(qtys[i] or 0) if i<len(qtys) else 0, unit=units[i] if i<len(units) else "pcs", reason=reasons[i] if i<len(reasons) else ""))
        db.session.flush(); audit(req.request_no,f"Created {req.request_type} material request for {p.code}","production"); db.session.commit()
        flash(f"{req.request_no} submitted","ok"); return redirect(url_for("materials"))
    return render_template("materials.html",projects=projects,requests=MaterialRequest.query.order_by(MaterialRequest.id.desc()).all())

@app.route("/materials/<int:rid>/edit",methods=["GET","POST"])
@login_required
def material_edit(rid):
    r=MaterialRequest.query.get_or_404(rid)
    if current_user() not in ("production","md"): flash("Only Production or MD can edit requests","error"); return redirect(url_for("materials"))
    if r.status in ("Approved","Issued","Cancelled","Closed"): flash("Request imefungwa; tumia additional request au cancel workflow","error"); return redirect(url_for("materials"))
    if request.method=="POST":
        old_items=", ".join(f"{x.item} x{x.quantity:g}" for x in r.items)
        for x in list(r.items): db.session.delete(x)
        items=request.form.getlist("item[]"); specs=request.form.getlist("specification[]"); qtys=request.form.getlist("quantity[]"); units=request.form.getlist("unit[]")
        for i,name in enumerate(items):
            if name.strip(): r.items.append(MaterialRequestItem(item=name.strip(),specification=specs[i] if i<len(specs) else "",quantity=float(qtys[i] or 0),unit=units[i] if i<len(units) else "pcs"))
        r.reason=request.form.get("reason",""); r.status="Returned" if r.status=="Returned" else r.status; r.updated_at=datetime.utcnow()
        audit(r.request_no,f"Edited request. Old items: {old_items}","-"); db.session.commit(); flash("Material request updated","ok"); return redirect(url_for("materials"))
    return render_template("material_edit.html",r=r)

@app.route("/materials/<int:rid>/action/<action>",methods=["POST"])
@login_required
def material_action(rid,action):
    r=MaterialRequest.query.get_or_404(rid)
    allowed={"approve":("production","md"),"return":("production","md"),"cancel":("production","md"),"issue":("production","store")}
    if current_user() not in allowed.get(action,()): flash("Huna ruhusa","error"); return redirect(url_for("materials"))
    if action=="approve": r.status="Approved"
    elif action=="return": r.status="Returned"
    elif action=="cancel": r.status="Cancelled"
    elif action=="issue": r.status="Issued"
    audit(r.request_no,action.title()+" material request","-"); r.updated_at=datetime.utcnow(); db.session.commit()
    return redirect(url_for("materials"))

# ---- Payment Requests ----
@app.route("/payment-requests",methods=["GET","POST"])
@login_required
def payment_requests():
    projects=Project.query.order_by(Project.name).all()
    if request.method=="POST":
        pr=PaymentRequest(request_no=next_no("PR",PaymentRequest),project_id=int(request.form["project_id"]) if request.form.get("project_id") else None,
            requested_by=current_user(),department=request.form.get("department",""),payee=request.form.get("payee",""),
            payment_type=request.form.get("payment_type",""),description=request.form.get("description",""),
            amount_requested=float(request.form.get("amount_requested") or 0),due_date=request.form.get("due_date",""),
            payment_method=request.form.get("payment_method",""),notes=request.form.get("notes",""),status="Submitted")
        db.session.add(pr); db.session.flush(); audit(pr.request_no,"Payment Request submitted","md"); db.session.commit()
        flash(f"{pr.request_no} submitted","ok"); return redirect(url_for("payment_requests"))
    return render_template("payment_requests.html",projects=projects,requests=PaymentRequest.query.order_by(PaymentRequest.id.desc()).all())

@app.route("/payment-requests/<int:rid>/approve",methods=["POST"])
@roles_required("md")
def approve_payment_request(rid):
    r=PaymentRequest.query.get_or_404(rid); r.amount_approved=float(request.form.get("amount_approved") or r.amount_requested); r.status="Approved"
    audit(r.request_no,f"Payment approved TZS {r.amount_approved:,.2f}","accounts"); db.session.commit(); return redirect(url_for("payment_requests"))

@app.route("/payment-requests/<int:rid>/pay",methods=["POST"])
@roles_required("accounts")
def pay_payment_request(rid):
    r=PaymentRequest.query.get_or_404(rid)
    if r.status not in ("Approved","Partially Paid"): flash("Payment request not approved","error"); return redirect(url_for("payment_requests"))
    amount=float(request.form.get("amount") or 0); remaining=max((r.amount_approved or r.amount_requested)-r.amount_paid,0)
    if amount<=0 or amount>remaining: flash("Amount exceeds remaining approved balance","error"); return redirect(url_for("payment_requests"))
    pay=Payment(payment_no=next_no("PAY",Payment),payment_request_id=r.id,payee=r.payee,project_id=r.project_id,amount=amount,method=request.form.get("method","Bank"),reference=request.form.get("reference",""),notes=request.form.get("notes",""),paid_by=current_user())
    db.session.add(pay); r.amount_paid += amount; r.status="Paid" if r.amount_paid >= (r.amount_approved or r.amount_requested) else "Partially Paid"
    audit(r.request_no,f"Payment made TZS {amount:,.2f}; cumulative TZS {r.amount_paid:,.2f}","accounts"); db.session.commit(); return redirect(url_for("payment_requests"))

# ---- Loans ----
@app.route("/loans",methods=["GET","POST"])
@login_required
def loans():
    projects=Project.query.order_by(Project.name).all()
    if request.method=="POST":
        l=Loan(loan_no=next_no("LOAN",Loan),project_id=int(request.form["project_id"]) if request.form.get("project_id") else None,
               person=request.form["person"],person_type=request.form.get("person_type","Fundi"),amount_requested=float(request.form.get("amount_requested") or 0),
               amount_issued=float(request.form.get("amount_issued") or 0),reason=request.form.get("reason",""),requested_by=current_user(),
               status="Issued" if float(request.form.get("amount_issued") or 0)>0 else "Requested")
        db.session.add(l); db.session.flush(); audit(l.loan_no,"Loan request/issue recorded","-"); db.session.commit(); return redirect(url_for("loans"))
    return render_template("loans.html",projects=projects,loans=Loan.query.order_by(Loan.id.desc()).all())

@app.route("/loans/<int:lid>/repay",methods=["POST"])
@login_required
def loan_repay(lid):
    l=Loan.query.get_or_404(lid); amount=float(request.form.get("amount") or 0)
    if amount<=0 or amount>l.balance: flash("Repayment exceeds loan balance","error"); return redirect(url_for("loans"))
    l.repayments.append(LoanRepayment(amount=amount,method=request.form.get("method","Cash"),reference=request.form.get("reference",""),paid_by=current_user()))
    db.session.flush(); l.status="Fully Paid" if l.balance<=0 else "Partially Paid"; audit(l.loan_no,f"Loan repayment TZS {amount:,.2f}; balance TZS {l.balance:,.2f}","-"); db.session.commit(); return redirect(url_for("loans"))

# ---- Fundi per project + installment labour payments ----
@app.route("/projects/<int:pid>/fundis",methods=["GET","POST"])
@login_required
def fundis(pid):
    p=Project.query.get_or_404(pid)
    if request.method=="POST":
        f=ProjectFundi(project_id=pid,name=request.form["name"],role=request.form.get("role","Fundi"),agreed_labour=float(request.form.get("agreed_labour") or 0))
        db.session.add(f); db.session.flush(); audit(p.code,f"Fundi added: {f.name}","-"); db.session.commit(); return redirect(url_for("fundis",pid=pid))
    return render_template("fundis.html",p=p,fundis=ProjectFundi.query.filter_by(project_id=pid).order_by(ProjectFundi.name).all())

@app.route("/fundis/<int:fid>/pay",methods=["POST"])
@login_required
def fundi_pay(fid):
    f=ProjectFundi.query.get_or_404(fid); amount=float(request.form.get("amount") or 0)
    if amount<=0 or amount>f.balance: flash("Payment exceeds remaining labour balance","error"); return redirect(url_for("fundis",pid=f.project_id))
    f.payments.append(LabourPayment(amount=amount,method=request.form.get("method","Bank"),reference=request.form.get("reference",""),paid_by=current_user(),notes=request.form.get("notes","")))
    db.session.flush(); f.status="Fully Paid" if f.balance<=0 else "Partially Paid"; audit(f"FUND-{f.id}",f"Labour payment to {f.name}: TZS {amount:,.2f}; balance TZS {f.balance:,.2f}","-"); db.session.commit()
    return redirect(url_for("fundis",pid=f.project_id))

@app.route("/audit")
@login_required
def audit_view(): return render_template("audit.html",logs=Audit.query.order_by(Audit.created_at.desc()).all())

@app.route("/settings",methods=["GET","POST"])
@roles_required("md")
def settings():
    # MD-only company settings, including uploaded logo and stamp.
    cfg={x.key:x.value for x in Setting.query.all()}
    if request.method=="POST":
        for key in ["company_name","phone","email","tin","vrn","address"]:
            val=request.form.get(key,"").strip()
            row=Setting.query.filter_by(key=key).first()
            if not row: row=Setting(key=key); db.session.add(row)
            row.value=val
        for field,key,prefix in [("logo","logo_path","logo"),("stamp","stamp_path","stamp")]:
            f=request.files.get(field)
            if f and f.filename:
                ext=f.filename.rsplit(".",1)[-1].lower() if "." in f.filename else ""
                if ext not in ALLOWED_UPLOADS:
                    flash(f"Invalid {field} file type. Use PNG, JPG, JPEG or WEBP.","error")
                    return redirect(url_for("settings"))
                filename=f"{prefix}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.{ext}"
                f.save(os.path.join(app.config["UPLOAD_DIR"], filename))
                row=Setting.query.filter_by(key=key).first()
                if not row: row=Setting(key=key); db.session.add(row)
                row.value=filename
        audit("SETTINGS","MD updated company settings/logo/stamp","md"); db.session.commit(); flash("Settings saved","ok"); return redirect(url_for("settings"))
    return render_template("settings.html",cfg=cfg)

@app.route("/uploads/<path:filename>")
def uploads(filename):
    return send_from_directory(app.config["UPLOAD_DIR"], filename)

@app.route("/profile/password",methods=["GET","POST"])
@login_required
def change_password():
    u=User.query.filter_by(username=current_user()).first_or_404()
    if request.method=="POST":
        old=request.form.get("old_password","")
        new=request.form.get("new_password","")
        confirm=request.form.get("confirm_password","")
        if not check_password_hash(u.password_hash,old):
            flash("Current password is incorrect.","error")
        elif len(new) < 8:
            flash("New password must be at least 8 characters.","error")
        elif new != confirm:
            flash("New passwords do not match.","error")
        else:
            u.password_hash=generate_password_hash(new); db.session.commit()
            audit("USER",f"Password changed for {u.username}","-"); db.session.commit()
            flash("Password changed successfully.","ok"); return redirect(url_for("dashboard"))
    return render_template("password.html")

class Setting(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    key=db.Column(db.String(80),unique=True,nullable=False)
    value=db.Column(db.Text,default="")

@app.route("/health")
def health():
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify(status="ok", database="connected")
    except Exception:
        return jsonify(status="error", database="unavailable"), 503

with app.app_context():
    db.create_all()
    for u,(r,pw) in USERS.items():
        if not User.query.filter_by(username=u).first():
            db.session.add(User(username=u,password_hash=generate_password_hash(pw),role=r))
    db.session.commit()

if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT", "8000")))
