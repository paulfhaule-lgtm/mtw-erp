import os
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY','dev-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL','sqlite:///mtw_erp.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

USERS = {
 'accounts': ('Accounts + Sales/Reception','accounts123'),
 'production': ('Production Director + Production','production123'),
 'store': ('Store Keeper + Procurement','store123'),
 'md': ('Managing Director','md123')
}

class User(db.Model):
 id=db.Column(db.Integer,primary_key=True); username=db.Column(db.String(80),unique=True,nullable=False); password_hash=db.Column(db.String(255),nullable=False); role=db.Column(db.String(120),nullable=False); active=db.Column(db.Boolean,default=True)
class Project(db.Model):
 id=db.Column(db.Integer,primary_key=True); code=db.Column(db.String(40),unique=True); name=db.Column(db.String(200)); client=db.Column(db.String(200)); contract_amount=db.Column(db.Float,default=0); status=db.Column(db.String(40),default='Active'); created_at=db.Column(db.DateTime,default=datetime.utcnow)
class Document(db.Model):
 id=db.Column(db.Integer,primary_key=True); doc_no=db.Column(db.String(60),unique=True); project=db.Column(db.String(200)); stage=db.Column(db.String(100)); holder=db.Column(db.String(100)); status=db.Column(db.String(40),default='Pending Action'); priority=db.Column(db.String(20),default='Normal'); comments=db.Column(db.Text); created_by=db.Column(db.String(80)); created_at=db.Column(db.DateTime,default=datetime.utcnow); updated_at=db.Column(db.DateTime,default=datetime.utcnow)
class Audit(db.Model):
 id=db.Column(db.Integer,primary_key=True); doc_no=db.Column(db.String(60)); action=db.Column(db.String(200)); by_user=db.Column(db.String(80)); routed_to=db.Column(db.String(100)); created_at=db.Column(db.DateTime,default=datetime.utcnow)
class Inventory(db.Model):
 id=db.Column(db.Integer,primary_key=True); sku=db.Column(db.String(60),unique=True); item=db.Column(db.String(200)); unit=db.Column(db.String(30)); qty=db.Column(db.Float,default=0); reorder_level=db.Column(db.Float,default=0)
class Invoice(db.Model):
 id=db.Column(db.Integer,primary_key=True); invoice_no=db.Column(db.String(60),unique=True); client=db.Column(db.String(200)); project=db.Column(db.String(200)); amount=db.Column(db.Float,default=0); paid=db.Column(db.Float,default=0); status=db.Column(db.String(40),default='Unpaid'); created_at=db.Column(db.DateTime,default=datetime.utcnow)

STAGES=[
 ('Customer Order','accounts'),('Job Card','production'),('Material Request','production'),('Stock Check','store'),
 ('Material Issue','production'),('Purchase Request','store'),('Quotation / Supplier','store'),('MD Approval','md'),('Purchase Order','store'),('Delivery','store'),('GRN','store'),
 ('Supplier Invoice','accounts'),('3-Way Check','accounts'),('Payment Voucher','accounts'),('MD Payment Approval','md'),('Payment','accounts'),('Proof of Payment','accounts'),('Accounting + Stock + Supplier Record','accounts')]
ROLE_NAME={k:v[0] for k,v in USERS.items()}

def current_user(): return session.get('username')
def login_required(f):
 @wraps(f)
 def w(*a,**kw):
  if not current_user(): return redirect(url_for('login'))
  return f(*a,**kw)
 return w

def can_stage(stage):
 for s,r in STAGES:
  if s==stage: return r==current_user()
 return False

def route_after(stage, stock_available=None):
 names=[s for s,r in STAGES]
 try: i=names.index(stage)
 except ValueError: return None
 if stage=='Stock Check':
  return ('Material Issue','production') if stock_available else ('Purchase Request','store')
 return STAGES[i+1] if i+1<len(STAGES) else None

@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  u=request.form['username'].strip().lower(); p=request.form['password']
  user=User.query.filter_by(username=u,active=True).first()
  if user and check_password_hash(user.password_hash,p): session['username']=u; return redirect(url_for('dashboard'))
  flash('Invalid username or password','error')
 return render_template('login.html')
@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
 projects=Project.query.order_by(Project.id.desc()).all(); docs=Document.query.order_by(Document.updated_at.desc()).limit(12).all(); invoices=Invoice.query.all()
 contract=sum(p.contract_amount or 0 for p in projects); billed=sum(i.amount or 0 for i in invoices); paid=sum(i.paid or 0 for i in invoices)
 return render_template('dashboard.html',user=current_user(),role=ROLE_NAME[current_user()],projects=projects,docs=docs,contract=contract,billed=billed,paid=paid,debt=billed-paid)

@app.route('/projects',methods=['GET','POST'])
@login_required
def projects():
 if request.method=='POST':
  p=Project(code=request.form['code'],name=request.form['name'],client=request.form['client'],contract_amount=float(request.form.get('contract_amount') or 0)); db.session.add(p); db.session.commit(); flash('Project created','ok'); return redirect(url_for('projects'))
 return render_template('projects.html',projects=Project.query.order_by(Project.id.desc()).all())

@app.route('/documents')
@login_required
def documents(): return render_template('documents.html',docs=Document.query.order_by(Document.updated_at.desc()).all(), stages=STAGES)

@app.route('/documents/new',methods=['POST'])
@login_required
def new_document():
 no=request.form.get('doc_no') or f"WO-{Document.query.count()+1:04d}"; project=request.form.get('project',''); d=Document(doc_no=no,project=project,stage='Customer Order',holder='accounts',created_by=current_user()); db.session.add(d); db.session.flush(); db.session.add(Audit(doc_no=no,action='Created / Customer Order',by_user=current_user(),routed_to='accounts')); db.session.commit(); flash('Workflow started and routed to Accounts','ok'); return redirect(url_for('documents'))

@app.route('/documents/<int:id>/complete',methods=['POST'])
@login_required
def complete(id):
 d=Document.query.get_or_404(id)
 if d.holder!=current_user(): flash('You are not the current holder of this document','error'); return redirect(url_for('documents'))
 stock=None
 if d.stage=='Stock Check': stock=request.form.get('stock_available')=='yes'
 nxt=route_after(d.stage,stock)
 d.status='Completed'; d.updated_at=datetime.utcnow();
 if nxt:
  d.stage,d.holder=nxt; d.status='Pending Action'; action=f"Completed {d.stage}" if False else 'Completed and routed'
  db.session.add(Audit(doc_no=d.doc_no,action=action,by_user=current_user(),routed_to=d.holder))
 else:
  db.session.add(Audit(doc_no=d.doc_no,action='Workflow completed',by_user=current_user(),routed_to='-'))
 db.session.commit(); return redirect(url_for('documents'))

@app.route('/inventory',methods=['GET','POST'])
@login_required
def inventory():
 if request.method=='POST':
  sku=request.form['sku']; item=Inventory.query.filter_by(sku=sku).first()
  if not item: item=Inventory(sku=sku,item=request.form['item'],unit=request.form.get('unit','pcs'),qty=float(request.form.get('qty') or 0),reorder_level=float(request.form.get('reorder') or 0)); db.session.add(item)
  else: item.qty += float(request.form.get('qty') or 0)
  db.session.commit(); return redirect(url_for('inventory'))
 return render_template('inventory.html',items=Inventory.query.order_by(Inventory.item).all())

@app.route('/invoices',methods=['GET','POST'])
@login_required
def invoices():
 if request.method=='POST':
  no=request.form.get('invoice_no') or f"INV-{Invoice.query.count()+1:05d}"; inv=Invoice(invoice_no=no,client=request.form['client'],project=request.form.get('project',''),amount=float(request.form.get('amount') or 0)); db.session.add(inv); db.session.commit(); return redirect(url_for('invoices'))
 return render_template('invoices.html',invoices=Invoice.query.order_by(Invoice.id.desc()).all())

@app.route('/audit')
@login_required
def audit(): return render_template('audit.html',logs=Audit.query.order_by(Audit.created_at.desc()).all())

@app.route('/health')
def health(): return jsonify(status='ok',database='connected')

with app.app_context():
 db.create_all()
 for u,(role,pw) in USERS.items():
  if not User.query.filter_by(username=u).first(): db.session.add(User(username=u,password_hash=generate_password_hash(pw),role=role))
 db.session.commit()

if __name__=='__main__': app.run(host='0.0.0.0',port=8000)
