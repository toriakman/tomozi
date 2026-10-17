from flask import Flask, render_template, request, redirect, url_for, jsonify, abort
import sqlite3, secrets, statistics
from pathlib import Path

app = Flask(__name__)
DB = Path(__file__).with_name("apple_tasting.db")

STARTER_APPLES = [
"Honeycrisp","Fuji","Gala","Granny Smith","Pink Lady","Cosmic Crisp","SweeTango","Jazz","Envy",
"Ambrosia","Golden Delicious","Red Delicious","McIntosh","Cortland","Jonathan","Jonagold",
"Braeburn","Opal","SnapDragon","EverCrisp"
]

def db():
    c=sqlite3.connect(DB)
    c.row_factory=sqlite3.Row
    return c

def init_db():
    c=db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS apples(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
    CREATE TABLE IF NOT EXISTS tastings(
      id INTEGER PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'DRAFT',
      public_token TEXT UNIQUE NOT NULL, admin_token TEXT UNIQUE NOT NULL, results_token TEXT UNIQUE NOT NULL
    );
    CREATE TABLE IF NOT EXISTS tasting_apples(
      id INTEGER PRIMARY KEY, tasting_id INTEGER NOT NULL, apple_id INTEGER NOT NULL, position INTEGER NOT NULL,
      UNIQUE(tasting_id, position)
    );
    CREATE TABLE IF NOT EXISTS participants(
      id INTEGER PRIMARY KEY, tasting_id INTEGER NOT NULL, name TEXT NOT NULL, token TEXT UNIQUE NOT NULL,
      submitted INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS entries(
      id INTEGER PRIMARY KEY, participant_id INTEGER NOT NULL, tasting_apple_id INTEGER NOT NULL,
      rating REAL, notes TEXT DEFAULT '', UNIQUE(participant_id,tasting_apple_id)
    );
    """)
    for a in STARTER_APPLES:
        c.execute("INSERT OR IGNORE INTO apples(name) VALUES(?)",(a,))
    c.commit(); c.close()

init_db()

def tasting_by_admin(token):
    c=db(); r=c.execute("SELECT * FROM tastings WHERE admin_token=?",(token,)).fetchone(); c.close()
    return r
def tasting_by_public(token):
    c=db(); r=c.execute("SELECT * FROM tastings WHERE public_token=?",(token,)).fetchone(); c.close()
    return r
def lineup(tid, reveal=False):
    c=db()
    rows=c.execute("""SELECT ta.id,ta.position,a.name FROM tasting_apples ta JOIN apples a ON a.id=ta.apple_id
                      WHERE ta.tasting_id=? ORDER BY ta.position""",(tid,)).fetchall()
    c.close()
    return [dict(r) if reveal else {"id":r["id"],"position":r["position"]} for r in rows]

@app.route("/")
def home():
    return render_template("home.html")

@app.post("/create")
def create():
    name=(request.form.get("name") or "Untitled Apple Tasting").strip()
    public,admin,results=[secrets.token_urlsafe(18) for _ in range(3)]
    c=db(); cur=c.execute("INSERT INTO tastings(name,public_token,admin_token,results_token) VALUES(?,?,?,?)",
                         (name,public,admin,results)); c.commit(); c.close()
    return redirect(url_for("setup", admin=admin))

@app.route("/host/<admin>/setup", methods=["GET","POST"])
def setup(admin):
    t=tasting_by_admin(admin)
    if not t: abort(404)
    c=db()
    if request.method=="POST":
        names=request.form.getlist("apple")
        names=[x.strip() for x in names if x.strip()][:50]
        c.execute("DELETE FROM tasting_apples WHERE tasting_id=?",(t["id"],))
        for pos,name in enumerate(names,1):
            c.execute("INSERT OR IGNORE INTO apples(name) VALUES(?)",(name,))
            aid=c.execute("SELECT id FROM apples WHERE name=?",(name,)).fetchone()["id"]
            c.execute("INSERT INTO tasting_apples(tasting_id,apple_id,position) VALUES(?,?,?)",(t["id"],aid,pos))
        c.commit(); c.close()
        return redirect(url_for("dashboard",admin=admin))
    apples=[r["name"] for r in c.execute("SELECT name FROM apples ORDER BY name").fetchall()]
    current=lineup(t["id"],True); c.close()
    return render_template("setup.html",t=t,apples=apples,current=current)

@app.route("/host/<admin>")
def dashboard(admin):
    t=tasting_by_admin(admin)
    if not t: abort(404)
    c=db()
    ps=c.execute("""SELECT p.*,
      (SELECT COUNT(*) FROM entries e WHERE e.participant_id=p.id AND (e.rating IS NOT NULL OR trim(e.notes)!='')) activity
      FROM participants p WHERE tasting_id=? ORDER BY id""",(t["id"],)).fetchall()
    c.close()
    active=[p for p in ps if p["activity"]>0]
    submitted=sum(1 for p in active if p["submitted"])
    return render_template("dashboard.html",t=t,ps=ps,active=len(active),submitted=submitted,
                           join_url=url_for("join",token=t["public_token"],_external=True),
                           results_url=url_for("results",token=t["results_token"],_external=True))

@app.post("/host/<admin>/status")
def status(admin):
    t=tasting_by_admin(admin)
    if not t: abort(404)
    status=request.form.get("status")
    if status not in ("DRAFT","OPEN","CLOSED"): abort(400)
    c=db(); c.execute("UPDATE tastings SET status=? WHERE id=?",(status,t["id"])); c.commit(); c.close()
    return redirect(url_for("dashboard",admin=admin))

@app.post("/host/<admin>/remove/<int:pid>")
def remove_participant(admin,pid):
    t=tasting_by_admin(admin)
    if not t: abort(404)
    c=db()
    p=c.execute("SELECT id FROM participants WHERE id=? AND tasting_id=?",(pid,t["id"])).fetchone()
    if p:
        c.execute("DELETE FROM entries WHERE participant_id=?",(pid,))
        c.execute("DELETE FROM participants WHERE id=?",(pid,)); c.commit()
    c.close()
    return redirect(url_for("dashboard",admin=admin))

@app.route("/t/<token>", methods=["GET","POST"])
def join(token):
    t=tasting_by_public(token)
    if not t: abort(404)
    if request.method=="POST":
        if t["status"]!="OPEN": return render_template("closed.html",t=t)
        name=(request.form.get("name") or "").strip()
        if not name: return render_template("join.html",t=t,error="Please enter your name.")
        pt=secrets.token_urlsafe(18)
        c=db(); c.execute("INSERT INTO participants(tasting_id,name,token) VALUES(?,?,?)",(t["id"],name,pt)); c.commit(); c.close()
        return redirect(url_for("taste",ptoken=pt))
    return render_template("join.html",t=t)

@app.route("/p/<ptoken>")
def taste(ptoken):
    c=db()
    p=c.execute("SELECT * FROM participants WHERE token=?",(ptoken,)).fetchone()
    if not p: c.close(); abort(404)
    t=c.execute("SELECT * FROM tastings WHERE id=?",(p["tasting_id"],)).fetchone()
    rows=c.execute("""SELECT ta.id,ta.position,e.rating,e.notes FROM tasting_apples ta
      LEFT JOIN entries e ON e.tasting_apple_id=ta.id AND e.participant_id=?
      WHERE ta.tasting_id=? ORDER BY ta.position""",(p["id"],t["id"])).fetchall()
    c.close()
    return render_template("taste.html",t=t,p=p,rows=rows)

@app.post("/api/p/<ptoken>/entry")
def save_entry(ptoken):
    data=request.get_json(force=True)
    c=db(); p=c.execute("SELECT * FROM participants WHERE token=?",(ptoken,)).fetchone()
    if not p: c.close(); abort(404)
    t=c.execute("SELECT * FROM tastings WHERE id=?",(p["tasting_id"],)).fetchone()
    if t["status"]!="OPEN": c.close(); return jsonify(error="Tasting is closed"),409
    taid=int(data["tasting_apple_id"])
    valid=c.execute("SELECT id FROM tasting_apples WHERE id=? AND tasting_id=?",(taid,t["id"])).fetchone()
    if not valid: c.close(); abort(400)
    rating=data.get("rating")
    if rating in ("",None): rating=None
    else:
        rating=round(float(rating),1)
        if rating<0 or rating>10: c.close(); abort(400)
    notes=(data.get("notes") or "")[:1000]
    c.execute("""INSERT INTO entries(participant_id,tasting_apple_id,rating,notes) VALUES(?,?,?,?)
      ON CONFLICT(participant_id,tasting_apple_id) DO UPDATE SET rating=excluded.rating,notes=excluded.notes""",
      (p["id"],taid,rating,notes))
    c.execute("UPDATE participants SET submitted=0 WHERE id=?",(p["id"],))
    c.commit(); c.close()
    return jsonify(ok=True)

@app.post("/p/<ptoken>/submit")
def submit(ptoken):
    c=db(); p=c.execute("SELECT * FROM participants WHERE token=?",(ptoken,)).fetchone()
    if not p: c.close(); abort(404)
    t=c.execute("SELECT * FROM tastings WHERE id=?",(p["tasting_id"],)).fetchone()
    if t["status"]!="OPEN": c.close(); return redirect(url_for("taste",ptoken=ptoken))
    total=c.execute("SELECT COUNT(*) n FROM tasting_apples WHERE tasting_id=?",(t["id"],)).fetchone()["n"]
    rated=c.execute("""SELECT COUNT(*) n FROM entries e JOIN tasting_apples ta ON ta.id=e.tasting_apple_id
        WHERE e.participant_id=? AND ta.tasting_id=? AND e.rating IS NOT NULL""",(p["id"],t["id"])).fetchone()["n"]
    if total and rated==total:
        c.execute("UPDATE participants SET submitted=1 WHERE id=?",(p["id"],)); c.commit()
    c.close()
    return redirect(url_for("taste",ptoken=ptoken))

@app.route("/results/<token>")
def results(token):
    c=db(); t=c.execute("SELECT * FROM tastings WHERE results_token=?",(token,)).fetchone()
    if not t: c.close(); abort(404)
    if t["status"]!="CLOSED": c.close(); return render_template("results_wait.html",t=t)
    rows=c.execute("""SELECT ta.position,a.name,AVG(e.rating) avg_rating,COUNT(e.rating) votes
      FROM tasting_apples ta JOIN apples a ON a.id=ta.apple_id
      LEFT JOIN entries e ON e.tasting_apple_id=ta.id
      LEFT JOIN participants p ON p.id=e.participant_id
      WHERE ta.tasting_id=? AND (p.submitted=1 OR p.submitted IS NULL)
      GROUP BY ta.id ORDER BY avg_rating DESC, ta.position ASC""",(t["id"],)).fetchall()
    c.close()
    return render_template("results.html",t=t,rows=rows)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=5000,debug=True)
