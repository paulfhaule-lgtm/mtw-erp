import os, io, csv, uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app=Flask(__name__)
app.config['SECRET_KEY']=os.getenv('SECRET_KEY','change-this-in-production')
db_url=os.getenv('DATABASE_URL','sqlite:///mtw_erp.db')
if db_url.startswith('postgres://'): db_url=db_url.replace('postgres://','postgresql://',1)
app.config['SQLALCHEMY_DATABASE_URI']=db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS']=False
app.config['MAX_CONTENT_LENGTH']=4*1024*1024
db=SQLAlchemy(app)
UPLOAD_DIR=os.path.join(app.root_path,'static','uploads'); os.makedirs(UPLOAD_DIR,exist_ok=True)

class User(db.Model):
    id=db.Column(db.Integer,primary_key=True); username=db.Column(db.String(80),unique=True,nullable=False)
    password_hash=db.Column(db.String(255),nullable=False); role=db.Column(db.String(40),default='Accounts Officer')
class Company(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(160),default='MTW'); address=db.Column(db.String(255)); phone=db.Column(db.String(80)); email=db.Column(db.String(120)); tin=db.Column(db.String(80)); vrn=db.Column(db.String(80)); logo=db.Column(db.String(255)); invoice_prefix=db.Column(db.String(20),default='INV')
class Project(db.Model):
    id=db.Column(db.Integer,primary_key=True); code=db.Column(db.String(40),unique=True,nullable=False); name=db.Column(db.String(160),nullable=False); client=db.Column(db.String(160)); location=db.Column(db.String(160)); start_date=db.Column(db.Date,default=date.today); end_date=db.Column(db.Date); status=db.Column(db.String(30),default='Active'); contract_amount=db.Column(db.Numeric(14,2),default=0); notes=db.Column(db.Text)
    workers=db.relationship('ProjectWorker',backref='project',cascade='all, delete-orphan'); materials=db.relationship('Material',backref='project',cascade='all, delete-orphan'); invoices=db.relationship('Invoice',backref='project')
class Worker(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(160),nullable=False); worker_type=db.Column(db.String(30),default='Fundi'); phone=db.Column(db.String(80)); role=db.Column(db.String(100)); agreed_rate=db.Column(db.Numeric(14,2),default=0); active=db.Column(db.Boolean,default=True)
class ProjectWorker(db.Model):
    id=db.Column(db.Integer,primary_key=True); project_id=db.Column(db.Integer,db.ForeignKey('project.id'),nullable=False); worker_id=db.Column(db.Integer,db.ForeignKey('worker.id'),nullable=False); job=db.Column(db.String(160)); agreed_amount=db.Column(db.Numeric(14,2),default=0); paid_amount=db.Column(db.Numeric(14,2),default=0); notes=db.Column(db.Text); worker=db.relationship('Worker')
class Material(db.Model):
    id=db.Column(db.Integer,primary_key=True); project_id=db.Column(db.Integer,db.ForeignKey('project.id'),nullable=False); item=db.Column(db.String(160),nullable=False); description=db.Column(db.String(255)); quantity=db.Column(db.Numeric(14,2),default=1); unit=db.Column(db.String(30),default='pcs'); amount=db.Column(db.Numeric(14,2),nullable=False); requested_by=db.Column(db.String(160)); txn_date=db.Column(db.Date,default=date.today); paid=db.Column(db.Numeric(14,2),default=0); supplier=db.Column(db.String(160))
class Loan(db.Model):
    id=db.Column(db.Integer,primary_key=True); person=db.Column(db.String(160),nullable=False); loan_type=db.Column(db.String(30),default='Staff Loan'); project_id=db.Column(db.Integer,db.ForeignKey('project.id')); request_date=db.Column(db.Date,default=date.today); amount=db.Column(db.Numeric(14,2),nullable=False); paid_amount=db.Column(db.Numeric(14,2),default=0); repayment_amount=db.Column(db.Numeric(14,2),default=0); status=db.Column(db.String(30),default='Open'); notes=db.Column(db.Text); project=db.relationship('Project')
class Payroll(db.Model):
    id=db.Column(db.Integer,primary_key=True); worker_id=db.Column(db.Integer,db.ForeignKey('worker.id')); pay_date=db.Column(db.Date,default=date.today); period=db.Column(db.String(20),nullable=False); gross=db.Column(db.Numeric(14,2),default=0); nssf_employee=db.Column(db.Numeric(14,2),default=0); paye=db.Column(db.Numeric(14,2),default=0); loan_deduction=db.Column(db.Numeric(14,2),default=0); other_deduction=db.Column(db.Numeric(14,2),default=0); net=db.Column(db.Numeric(14,2),default=0); nssf_employer=db.Column(db.Numeric(14,2),default=0); sdl=db.Column(db.Numeric(14,2),default=0); wcf=db.Column(db.Numeric(14,2),default=0); employer_cost=db.Column(db.Numeric(14,2),default=0); paid=db.Column(db.Numeric(14,2),default=0); notes=db.Column(db.Text); worker=db.relationship('Worker')
class StatutorySetting(db.Model):
    id=db.Column(db.Integer,primary_key=True); nssf_employee_rate=db.Column(db.Numeric(6,3),default=0); nssf_employer_rate=db.Column(db.Numeric(6,3),default=0); sdl_rate=db.Column(db.Numeric(6,3),default=0); wcf_rate=db.Column(db.Numeric(6,3),default=0); paye_enabled=db.Column(db.Boolean,default=True); effective_from=db.Column(db.Date,default=date.today)
class ExpenseCategory(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(120),unique=True,nullable=False); active=db.Column(db.Boolean,default=True)
class Transaction(db.Model):
    id=db.Column(db.Integer,primary_key=True); txn_date=db.Column(db.Date,default=date.today,nullable=False); txn_type=db.Column(db.String(20),nullable=False); category=db.Column(db.String(120),nullable=False); description=db.Column(db.String(255),nullable=False); amount=db.Column(db.Numeric(14,2),nullable=False); payment_method=db.Column(db.String(40),default='Cash'); reference=db.Column(db.String(100)); project_id=db.Column(db.Integer,db.ForeignKey('project.id')); notes=db.Column(db.Text); project=db.relationship('Project')
class Invoice(db.Model):
    id=db.Column(db.Integer,primary_key=True); number=db.Column(db.String(60),unique=True,nullable=False); project_id=db.Column(db.Integer,db.ForeignKey('project.id')); customer=db.Column(db.String(160),nullable=False); issue_date=db.Column(db.Date,default=date.today); due_date=db.Column(db.Date); status=db.Column(db.String(30),default='Unpaid'); tax_rate=db.Column(db.Numeric(6,2),default=0); notes=db.Column(db.Text); items=db.relationship('InvoiceItem',backref='invoice',cascade='all, delete-orphan')
class InvoiceItem(db.Model):
    id=db.Column(db.Integer,primary_key=True); invoice_id=db.Column(db.Integer,db.ForeignKey('invoice.id'),nullable=False); description=db.Column(db.String(255)); quantity=db.Column(db.Numeric(14,2),default=1); rate=db.Column(db.Numeric(14,2),default=0); amount=db.Column(db.Numeric(14,2),default=0)

DEFAULT_CATS=['Materials','Fundi/Labour','Salary','Transport','Fuel','Office Rent','Electricity','Water','Internet','Office Supplies','Repairs/Maintenance','Bank Charges','Taxes','Loan/Staff Advance','Other Expense','Sales/Income','Client Payment','Other Income']

def expense_categories():
    rows=ExpenseCategory.query.filter_by(active=True).order_by(ExpenseCategory.name).all()
    return [x.name for x in rows] if rows else DEFAULT_CATS

def statutory():
    return StatutorySetting.query.order_by(StatutorySetting.effective_from.desc()).first() or StatutorySetting(nssf_employee_rate=0,nssf_employer_rate=0,sdl_rate=0,wcf_rate=0,paye_enabled=True)

def calculate_paye(gross):
    # PAYE is intentionally configurable rather than hard-coded; enter the applicable monthly PAYE amount/rules in Payroll Settings.
    return Decimal('0')

def company(): return Company.query.first()
def money(x): return Decimal(str(x or 0))
def login_required(f):
    @wraps(f)
    def w(*a,**kw):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*a,**kw)
    return w
@app.before_request
def guard():
    if request.endpoint not in {'login','static','health'} and 'user_id' not in session: return redirect(url_for('login'))
@app.context_processor
def globals_(): return {'company':company(),'today':date.today()}

@app.route('/health')
def health():
    try: db.session.execute(db.text('SELECT 1')); return jsonify(status='ok',database='connected')
    except Exception as e: return jsonify(status='error',database='disconnected',error=str(e)),503
@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        u=User.query.filter_by(username=request.form.get('username','').strip()).first()
        if u and check_password_hash(u.password_hash,request.form.get('password','')):
            session.update(user_id=u.id,username=u.username,role=u.role); return redirect(url_for('dashboard'))
        flash('Username au password si sahihi.','danger')
    return render_template('login.html')
@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

def period_dates(p):
    t=date.today()
    if p=='day': return t,t
    if p=='week': s=t-timedelta(days=t.weekday()); return s,s+timedelta(days=6)
    if p=='month': s=t.replace(day=1); n=date(s.year+1,1,1) if s.month==12 else date(s.year,s.month+1,1); return s,n-timedelta(days=1)
    return date(t.year,1,1),date(t.year,12,31)
def totals(s,e):
    inc=db.session.query(db.func.coalesce(db.func.sum(Transaction.amount),0)).filter(Transaction.txn_type=='Income',Transaction.txn_date.between(s,e)).scalar()
    exp=db.session.query(db.func.coalesce(db.func.sum(Transaction.amount),0)).filter(Transaction.txn_type=='Expense',Transaction.txn_date.between(s,e)).scalar()
    return money(inc),money(exp)

def project_stats(p):
    materials=sum((money(x.amount) for x in p.materials),Decimal(0)); labour=sum((money(x.agreed_amount) for x in p.workers),Decimal(0)); paid_labour=sum((money(x.paid_amount) for x in p.workers),Decimal(0))
    tx_exp=money(db.session.query(db.func.coalesce(db.func.sum(Transaction.amount),0)).filter(Transaction.project_id==p.id,Transaction.txn_type=='Expense').scalar())
    inv=sum((sum((money(i.amount) for i in x.items),Decimal(0)) for x in p.invoices),Decimal(0))
    return materials,labour,paid_labour,tx_exp,inv

@app.route('/')
def dashboard():
    cards={p:dict(zip(['start','end','income','expense','balance'],(*period_dates(p),*totals(*period_dates(p)),))) for p in ['day','week','month','year']}
    projects=Project.query.order_by(Project.id.desc()).limit(8).all(); open_loans=money(db.session.query(db.func.coalesce(db.func.sum(Loan.amount-Loan.paid_amount),0)).filter(Loan.status!='Closed').scalar())
    return render_template('dashboard.html',cards=cards,projects=projects,open_loans=open_loans)

@app.route('/projects')
def projects(): return render_template('projects.html',projects=Project.query.order_by(Project.id.desc()).all())
@app.route('/projects/new',methods=['GET','POST'])
def project_new():
    if request.method=='POST':
        p=Project(code=request.form['code'].strip(),name=request.form['name'].strip(),client=request.form.get('client'),location=request.form.get('location'),contract_amount=Decimal(request.form.get('contract_amount') or 0),start_date=datetime.strptime(request.form['start_date'],'%Y-%m-%d').date(),status=request.form.get('status','Active'),notes=request.form.get('notes'))
        db.session.add(p); db.session.commit(); flash('Project imeongezwa.','success'); return redirect(url_for('project_detail',pid=p.id))
    return render_template('project_form.html')
@app.route('/projects/<int:pid>')
def project_detail(pid):
    p=db.get_or_404(Project,pid); stats=project_stats(p); workers=Worker.query.filter_by(active=True).all(); return render_template('project_detail.html',p=p,stats=stats,workers=workers)
@app.route('/projects/<int:pid>/worker',methods=['POST'])
def add_project_worker(pid):
    x=ProjectWorker(project_id=pid,worker_id=int(request.form['worker_id']),job=request.form.get('job'),agreed_amount=Decimal(request.form.get('agreed_amount') or 0),paid_amount=Decimal(request.form.get('paid_amount') or 0),notes=request.form.get('notes')); db.session.add(x); db.session.commit(); return redirect(url_for('project_detail',pid=pid))
@app.route('/projects/<int:pid>/material',methods=['POST'])
def add_material(pid):
    x=Material(project_id=pid,item=request.form['item'],description=request.form.get('description'),quantity=Decimal(request.form.get('quantity') or 1),unit=request.form.get('unit','pcs'),amount=Decimal(request.form.get('amount') or 0),requested_by=request.form.get('requested_by'),supplier=request.form.get('supplier'),txn_date=datetime.strptime(request.form['txn_date'],'%Y-%m-%d').date(),paid=Decimal(request.form.get('paid') or 0)); db.session.add(x); db.session.commit(); return redirect(url_for('project_detail',pid=pid))

@app.route('/workers')
def workers(): return render_template('workers.html',workers=Worker.query.order_by(Worker.name).all())
@app.route('/workers/new',methods=['GET','POST'])
def worker_new():
    if request.method=='POST':
        db.session.add(Worker(name=request.form['name'],worker_type=request.form.get('worker_type','Fundi'),phone=request.form.get('phone'),role=request.form.get('role'),agreed_rate=Decimal(request.form.get('agreed_rate') or 0))); db.session.commit(); flash('Fundi/Staff ameongezwa.','success'); return redirect(url_for('workers'))
    return render_template('worker_form.html')

@app.route('/loans')
def loans(): return render_template('loans.html',loans=Loan.query.order_by(Loan.id.desc()).all())
@app.route('/loans/new',methods=['GET','POST'])
def loan_new():
    if request.method=='POST':
        amount=Decimal(request.form['amount']); paid=Decimal(request.form.get('paid_amount') or 0); db.session.add(Loan(person=request.form['person'],loan_type=request.form.get('loan_type','Staff Loan'),project_id=int(request.form['project_id']) if request.form.get('project_id') else None,request_date=datetime.strptime(request.form['request_date'],'%Y-%m-%d').date(),amount=amount,paid_amount=paid,repayment_amount=Decimal(request.form.get('repayment_amount') or 0),status='Closed' if paid>=amount else 'Open',notes=request.form.get('notes'))); db.session.commit(); return redirect(url_for('loans'))
    return render_template('loan_form.html',projects=Project.query.all())

@app.route('/payroll')
def payroll():
    st=statutory(); return render_template('payroll.html',rows=Payroll.query.order_by(Payroll.pay_date.desc()).all(),workers=Worker.query.filter_by(active=True).all(),st=st)

@app.route('/payroll/new',methods=['POST'])
def payroll_new():
    gross=money(request.form.get('gross')); st=statutory()
    nssf_e=gross*money(st.nssf_employee_rate)/Decimal(100); nssf_er=gross*money(st.nssf_employer_rate)/Decimal(100); sdl=gross*money(st.sdl_rate)/Decimal(100); wcf=gross*money(st.wcf_rate)/Decimal(100)
    paye=money(request.form.get('paye'))
    loan=money(request.form.get('loan_deduction')); other=money(request.form.get('other_deduction')); net=gross-nssf_e-paye-loan-other; paid=money(request.form.get('paid')); employer_cost=gross+nssf_er+sdl+wcf
    db.session.add(Payroll(worker_id=int(request.form['worker_id']),pay_date=datetime.strptime(request.form['pay_date'],'%Y-%m-%d').date(),period=request.form['period'],gross=gross,nssf_employee=nssf_e,paye=paye,loan_deduction=loan,other_deduction=other,net=net,nssf_employer=nssf_er,sdl=sdl,wcf=wcf,employer_cost=employer_cost,paid=paid,notes=request.form.get('notes'))); db.session.commit(); flash('Payroll imehifadhiwa pamoja na statutory calculations.','success'); return redirect(url_for('payroll'))

@app.route('/payroll/settings',methods=['POST'])
def payroll_settings():
    st=statutory(); st.nssf_employee_rate=money(request.form.get('nssf_employee_rate')); st.nssf_employer_rate=money(request.form.get('nssf_employer_rate')); st.sdl_rate=money(request.form.get('sdl_rate')); st.wcf_rate=money(request.form.get('wcf_rate')); st.paye_enabled=bool(request.form.get('paye_enabled')); st.effective_from=datetime.strptime(request.form['effective_from'],'%Y-%m-%d').date(); db.session.add(st) if not st.id else None; db.session.commit(); flash('Payroll statutory settings zimehifadhiwa.','success'); return redirect(url_for('payroll'))

@app.route('/transactions')
def transactions():
    q=Transaction.query
    if request.args.get('type') in ('Income','Expense'): q=q.filter_by(txn_type=request.args['type'])
    if request.args.get('project_id'): q=q.filter_by(project_id=int(request.args['project_id']))
    if request.args.get('start'): q=q.filter(Transaction.txn_date>=datetime.strptime(request.args['start'],'%Y-%m-%d').date())
    if request.args.get('end'): q=q.filter(Transaction.txn_date<=datetime.strptime(request.args['end'],'%Y-%m-%d').date())
    rows=q.order_by(Transaction.txn_date.desc(),Transaction.id.desc()).all(); inc=sum((money(x.amount) for x in rows if x.txn_type=='Income'),Decimal(0)); exp=sum((money(x.amount) for x in rows if x.txn_type=='Expense'),Decimal(0)); return render_template('transactions.html',rows=rows,income=inc,expense=exp,balance=inc-exp,projects=Project.query.all())
@app.route('/transactions/new',methods=['GET','POST'])
def transaction_new():
    if request.method=='POST':
        db.session.add(Transaction(txn_date=datetime.strptime(request.form['txn_date'],'%Y-%m-%d').date(),txn_type=request.form['txn_type'],category=request.form['category'],description=request.form['description'],amount=Decimal(request.form['amount']),payment_method=request.form.get('payment_method','Cash'),reference=request.form.get('reference'),project_id=int(request.form['project_id']) if request.form.get('project_id') else None,notes=request.form.get('notes'))); db.session.commit(); flash('Transaction imehifadhiwa.','success'); return redirect(url_for('transactions'))
    return render_template('transaction_form.html',categories=expense_categories(),projects=Project.query.all())

@app.route('/expense-categories',methods=['GET','POST'])
def expense_categories_page():
    if request.method=='POST':
        name=request.form.get('name','').strip()
        if name:
            exists=ExpenseCategory.query.filter(db.func.lower(ExpenseCategory.name)==name.lower()).first()
            if not exists: db.session.add(ExpenseCategory(name=name)); db.session.commit(); flash('Expense category imeongezwa.','success')
        return redirect(url_for('expense_categories_page'))
    return render_template('expense_categories.html',categories=ExpenseCategory.query.order_by(ExpenseCategory.name).all())

@app.route('/invoices')
def invoices(): return render_template('invoices.html',invoices=Invoice.query.order_by(Invoice.issue_date.desc()).all())
@app.route('/invoices/new',methods=['GET','POST'])
def invoice_new():
    if request.method=='POST':
        c=company() or Company(name='MTW');
        if not c.id: db.session.add(c); db.session.flush()
        num=f"{c.invoice_prefix or 'INV'}-{date.today().strftime('%Y%m%d')}-{Invoice.query.count()+1:04d}"
        inv=Invoice(number=num,project_id=int(request.form['project_id']) if request.form.get('project_id') else None,customer=request.form['customer'],issue_date=datetime.strptime(request.form['issue_date'],'%Y-%m-%d').date(),due_date=datetime.strptime(request.form['due_date'],'%Y-%m-%d').date() if request.form.get('due_date') else None,tax_rate=Decimal(request.form.get('tax_rate') or 0),notes=request.form.get('notes'))
        db.session.add(inv); db.session.flush()
        desc=request.form.getlist('description'); qty=request.form.getlist('quantity'); rate=request.form.getlist('rate')
        for d,q,r in zip(desc,qty,rate):
            if d.strip(): inv.items.append(InvoiceItem(description=d,quantity=Decimal(q or 1),rate=Decimal(r or 0),amount=Decimal(q or 1)*Decimal(r or 0)))
        db.session.commit(); return redirect(url_for('invoice_view',iid=inv.id))
    return render_template('invoice_form.html',projects=Project.query.all())
def invoice_totals(inv):
    sub=sum((money(i.amount) for i in inv.items),Decimal(0)); tax=sub*money(inv.tax_rate)/Decimal(100); return sub,tax,sub+tax
@app.route('/invoices/<int:iid>')
def invoice_view(iid):
    inv=db.get_or_404(Invoice,iid); return render_template('invoice.html',inv=inv,totals=invoice_totals(inv))
@app.route('/invoices/<int:iid>/download')
def invoice_download(iid):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    inv=db.get_or_404(Invoice,iid); c=company(); sub,tax,total=invoice_totals(inv); buf=io.BytesIO(); pdf=canvas.Canvas(buf,pagesize=A4); w,h=A4
    pdf.setFont('Helvetica-Bold',16); pdf.drawString(20*mm,h-22*mm,c.name if c else 'MTW'); pdf.setFont('Helvetica',9); y=h-30*mm
    if c:
        for line in [c.address,c.phone,c.email,f'TIN: {c.tin or ""}   VRN: {c.vrn or ""}']:
            if line: pdf.drawString(20*mm,y,line); y-=5*mm
    pdf.setFont('Helvetica-Bold',14); pdf.drawRightString(w-20*mm,h-22*mm,'INVOICE'); pdf.setFont('Helvetica',10); pdf.drawRightString(w-20*mm,h-30*mm,inv.number)
    y=min(y,h-45*mm); pdf.drawString(20*mm,y,f'Bill To: {inv.customer}'); y-=10*mm
    pdf.setFont('Helvetica-Bold',9); pdf.drawString(20*mm,y,'Description'); pdf.drawRightString(w-85*mm,y,'Qty'); pdf.drawRightString(w-55*mm,y,'Rate'); pdf.drawRightString(w-20*mm,y,'Amount'); y-=6*mm; pdf.setFont('Helvetica',9)
    for it in inv.items:
        pdf.drawString(20*mm,y,it.description[:55]); pdf.drawRightString(w-85*mm,y,f'{it.quantity:g}'); pdf.drawRightString(w-55*mm,y,f'{money(it.rate):,.2f}'); pdf.drawRightString(w-20*mm,y,f'{money(it.amount):,.2f}'); y-=6*mm
    y-=5*mm; pdf.drawRightString(w-20*mm,y,f'Subtotal: {sub:,.2f}'); y-=6*mm; pdf.drawRightString(w-20*mm,y,f'Tax: {tax:,.2f}'); y-=6*mm; pdf.setFont('Helvetica-Bold',10); pdf.drawRightString(w-20*mm,y,f'TOTAL TZS: {total:,.2f}'); pdf.save(); buf.seek(0); return send_file(buf,mimetype='application/pdf',as_attachment=True,download_name=f'{inv.number}.pdf')

@app.route('/reports')
def reports():
    p=request.args.get('period','month'); s,e=period_dates(p); inc,exp=totals(s,e); bycat=db.session.query(Transaction.txn_type,Transaction.category,db.func.sum(Transaction.amount)).filter(Transaction.txn_date.between(s,e)).group_by(Transaction.txn_type,Transaction.category).order_by(Transaction.txn_type).all(); byproj=db.session.query(Project.name,db.func.coalesce(db.func.sum(Transaction.amount),0)).join(Transaction,Transaction.project_id==Project.id).filter(Transaction.txn_date.between(s,e),Transaction.txn_type=='Expense').group_by(Project.name).all(); return render_template('reports.html',period=p,start=s,end=e,income=inc,expense=exp,balance=inc-exp,bycat=bycat,byproj=byproj)
@app.route('/export.csv')
def export_csv():
    out=io.StringIO(); w=csv.writer(out); w.writerow(['Date','Type','Category','Description','Amount','Payment Method','Reference','Project'])
    for t in Transaction.query.order_by(Transaction.txn_date).all(): w.writerow([t.txn_date,t.txn_type,t.category,t.description,t.amount,t.payment_method,t.reference,t.project.name if t.project else ''])
    return send_file(io.BytesIO(out.getvalue().encode('utf-8-sig')),mimetype='text/csv',as_attachment=True,download_name='mtw_transactions.csv')

@app.route('/settings',methods=['GET','POST'])
def settings():
    c=company()
    if not c: c=Company(name='MTW'); db.session.add(c); db.session.commit()
    if request.method=='POST':
        c.name=request.form['name']; c.address=request.form.get('address'); c.phone=request.form.get('phone'); c.email=request.form.get('email'); c.tin=request.form.get('tin'); c.vrn=request.form.get('vrn'); c.invoice_prefix=request.form.get('invoice_prefix','INV')
        f=request.files.get('logo')
        if f and f.filename:
            ext=os.path.splitext(secure_filename(f.filename))[1].lower(); name=f'logo_{uuid.uuid4().hex}{ext}'; f.save(os.path.join(UPLOAD_DIR,name)); c.logo=name
        db.session.commit(); flash('Company settings zimehifadhiwa.','success'); return redirect(url_for('settings'))
    return render_template('settings.html',c=c)

def migrate_schema():
    """Small additive migration for existing Railway/PostgreSQL or SQLite databases."""
    inspector=db.inspect(db.engine)
    tables=inspector.get_table_names()
    if 'payroll' in tables:
        cols={c['name'] for c in inspector.get_columns('payroll')}
        additions={
            'nssf_employee':'NUMERIC(14,2)', 'paye':'NUMERIC(14,2)', 'nssf_employer':'NUMERIC(14,2)',
            'sdl':'NUMERIC(14,2)', 'wcf':'NUMERIC(14,2)', 'employer_cost':'NUMERIC(14,2)'
        }
        for col,typ in additions.items():
            if col not in cols:
                db.session.execute(db.text(f'ALTER TABLE payroll ADD COLUMN {col} {typ} DEFAULT 0'))
    db.session.commit()

with app.app_context():
    db.create_all()
    migrate_schema()
    if not User.query.filter_by(username='accounts').first():
        db.session.add(User(username='accounts',password_hash=generate_password_hash(os.getenv('ACCOUNTS_PASSWORD','ChangeMe123!')),role='Accounts Officer'))
    if not Company.query.first(): db.session.add(Company(name='MTW',address=''))
    if not StatutorySetting.query.first(): db.session.add(StatutorySetting(nssf_employee_rate=0,nssf_employer_rate=0,sdl_rate=0,wcf_rate=0,paye_enabled=True,effective_from=date.today()))
    if not ExpenseCategory.query.first():
        for cat in DEFAULT_CATS: db.session.add(ExpenseCategory(name=cat))
    db.session.commit()

if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT',5000)),debug=False)
