from datetime import datetime
import csv
from io import StringIO
from functools import wraps
import os

from dotenv import load_dotenv

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    Response,
    session,
)
from models import db, Firefighter, TestResult
from sqlalchemy import or_


# Charge le fichier .env si présent (local / prod)
load_dotenv()


def create_app():
    app = Flask(__name__)

    # --- Config DB (Railway MySQL via .env, sinon SQLite local) ---
    db_url = os.getenv("DATABASE_URL", "").strip()

    # Si on colle une URL "mysql://", SQLAlchemy veut "mysql+pymysql://"
    if db_url.startswith("mysql://"):
        db_url = db_url.replace("mysql://", "mysql+pymysql://", 1)

    if db_url:
        app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///pompiers.db"

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # --- Sécurité / Login depuis .env ---
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
    app.config["LOGIN_USERNAME"] = os.getenv("LOGIN_USERNAME", "admin2026")
    app.config["LOGIN_PASSWORD"] = os.getenv("LOGIN_PASSWORD", "motdepasse2026")

    db.init_app(app)

    with app.app_context():
        db.create_all()
    GRADES = [
        "Sapeur",
        "Caporal",
        "Caporal-chef",
        "Sergent",
        "Sergent-chef",
        "Adjudant",
        "Adjudant-chef",
        "Lieutenant",
        "Capitaine",
        "Commandant",
        "Lieutenant-colonel",
        "Colonel",
    ]

    CASERNES = [
        "Digoin",
        "Le Creusot",
        "Chalon sur Saône",
        "Macon",
        "Loisy",
        "Crissey",
        "Cuiseaux",
    ]

    # --- Auth decorator ---
    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("logged_in"):
                return redirect(url_for("login", next=request.path))
            return view(*args, **kwargs)

        return wrapped

    # --- Login / Logout ---
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()

            if (
                username == app.config["LOGIN_USERNAME"]
                and password == app.config["LOGIN_PASSWORD"]
            ):
                session["logged_in"] = True
                flash("Connexion réussie.", "success")
                nxt = request.args.get("next")
                return redirect(nxt or url_for("agents"))

            flash("Identifiants incorrects.", "danger")
            return render_template("login.html")

        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        flash("Déconnecté.", "warning")
        return redirect(url_for("login"))

    # ---- Home ----
    @app.route("/")
    @login_required
    def index():
        return redirect(url_for("agents"))

    # ---- AGENTS ----
    @app.route("/agents")
    @login_required
    def agents():
        q = request.args.get("q", "").strip()
        searched = bool(q)

        query = Firefighter.query
        if q:
            # Recherche "intelligente" (1 char = commence par, sinon contient)
            if len(q) == 1:
                like = f"{q}%"
            else:
                like = f"%{q}%"

            query = query.filter(
                (Firefighter.nom.ilike(like))
                | (Firefighter.prenom.ilike(like))
                | (Firefighter.matricule.ilike(like))
            )

        data = query.order_by(Firefighter.nom.asc(), Firefighter.prenom.asc()).all()
        return render_template("agents.html", agents=data, q=q, searched=searched)

    # ---- EXPORT CSV (AGENTS) ----

    @app.route("/export.csv")
    @login_required
    def export_all_csv():
        q = request.args.get("q", "").strip()

        # On exporte toutes les lignes de TestResult,
        # en joignant les infos de l'agent.
        query = db.session.query(TestResult, Firefighter).join(
            Firefighter, Firefighter.id == TestResult.firefighter_id
        )

        # Filtre recherche (comme ta page Agents)
        if q:
            like = f"%{q}%"
            query = query.filter(
                or_(
                    Firefighter.nom.ilike(like),
                    Firefighter.prenom.ilike(like),
                    Firefighter.matricule.ilike(like),
                )
            )

        # Trier par agent puis date (du plus récent au plus ancien)
        rows = query.order_by(
            Firefighter.nom.asc(),
            Firefighter.prenom.asc(),
            TestResult.date_realisation.desc(),
        ).all()

        output = StringIO()
        writer = csv.writer(output)

        # En-têtes CSV
        writer.writerow(
            [
                "Matricule",
                "Nom",
                "Prénom",
                "Grade",
                "Caserne",
                "Date",
                "Assis-debout G",
                "Assis-debout D",
                "Heel raise G",
                "Heel raise D",
                "Side hop G",
                "Side hop D",
                "Wall test G",
                "Wall test D",
            ]
        )

        def fmt(v):
            return "" if v is None else str(v)

        for r, a in rows:
            writer.writerow(
                [
                    a.matricule or "",
                    a.nom or "",
                    a.prenom or "",
                    a.grade or "",
                    a.caserne or "",
                    (
                        r.date_realisation.strftime("%Y-%m-%d")
                        if r.date_realisation
                        else ""
                    ),
                    fmt(r.assis_debout_g),
                    fmt(r.assis_debout_d),
                    fmt(r.heel_raise_g),
                    fmt(r.heel_raise_d),
                    fmt(r.side_hop_g),
                    fmt(r.side_hop_d),
                    fmt(r.wall_test_g),
                    fmt(r.wall_test_d),
                ]
            )

        csv_content = output.getvalue()
        output.close()

        return Response(
            csv_content,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=agents_tests.csv"},
        )

    @app.route("/agents/new", methods=["GET", "POST"])
    @login_required
    def agent_new():
        if request.method == "POST":
            agent = Firefighter(
                matricule=request.form.get("matricule") or None,
                nom=request.form.get("nom", "").strip(),
                prenom=request.form.get("prenom", "").strip(),
                grade=request.form.get("grade") or None,
                caserne=request.form.get("caserne") or None,
            )

            if not agent.nom or not agent.prenom:
                flash("Nom et prénom sont obligatoires.", "danger")
                return render_template("agent_form.html", agent=None)

            db.session.add(agent)
            db.session.commit()
            flash("Agent ajouté.", "success")
            return redirect(url_for("agents"))

        return render_template(
            "agent_form.html", agent=None, grades=GRADES, casernes=CASERNES
        )

    @app.route("/agents/<int:agent_id>/delete", methods=["POST"])
    @login_required
    def agent_delete(agent_id):
        agent = Firefighter.query.get_or_404(agent_id)
        db.session.delete(agent)
        db.session.commit()
        flash("Agent supprimé.", "warning")
        return redirect(url_for("agents"))

    # ---- DETAILS + RESULTATS ----
    @app.route("/agents/<int:agent_id>")
    @login_required
    def agent_detail(agent_id):
        agent = Firefighter.query.get_or_404(agent_id)
        results = (
            TestResult.query.filter_by(firefighter_id=agent.id)
            .order_by(TestResult.date_realisation.desc())
            .all()
        )
        return render_template("agent_detail.html", agent=agent, results=results)

    # ========= ROUTE /analytics COMPLETE (vue individuelle + vue globale "dans le temps") =========
    @app.route("/analytics")
    @login_required
    def analytics():
        # mode: individual (défaut) ou global
        view_mode = request.args.get("view", "individual").strip()

        # Liste agents (dropdown vue individuelle)
        agents = Firefighter.query.order_by(
            Firefighter.nom.asc(), Firefighter.prenom.asc()
        ).all()

        # Définition des tests
        tests = [
            {"key": "assis_debout", "label": "Assis-debout"},
            {"key": "heel_raise", "label": "Heel raise"},
            {"key": "side_hop", "label": "Side hop"},
            {"key": "wall_test", "label": "Wall test"},
        ]
        test_keys = [t["key"] for t in tests]

        # -----------------------------
        # VUE INDIVIDUELLE (inchangée)
        # -----------------------------
        agent_id = request.args.get("agent_id", "").strip()
        selected_agent = None

        selected_test = request.args.get("test", "assis_debout").strip()
        if selected_test not in test_keys:
            selected_test = "assis_debout"

        test_label = next(t["label"] for t in tests if t["key"] == selected_test)

        points = []
        if agent_id.isdigit():
            selected_agent = Firefighter.query.get(int(agent_id))
            if selected_agent:
                results = (
                    TestResult.query.filter_by(firefighter_id=selected_agent.id)
                    .order_by(TestResult.date_realisation.asc())
                    .all()
                )

                col_g = f"{selected_test}_g"
                col_d = f"{selected_test}_d"

                for r in results:
                    points.append(
                        {
                            "date": r.date_realisation.strftime("%Y-%m-%d"),
                            "g": getattr(r, col_g, None),
                            "d": getattr(r, col_d, None),
                        }
                    )

        # -----------------------------
        # VUE GLOBALE "DANS LE TEMPS"
        # => pour un test choisi, on calcule pour CHAQUE DATE :
        #    déficit moyen (%) sur tous les agents ayant une valeur ce jour-là
        # -----------------------------
        global_test = request.args.get("global_test", "assis_debout").strip()
        if global_test not in test_keys:
            global_test = "assis_debout"

        global_label = next(t["label"] for t in tests if t["key"] == global_test)

        global_points = []  # [{"date": "YYYY-MM-DD", "avg_deficit": 12.3, "n": 8}, ...]
        global_summary = None  # ex: moyenne globale sur toute la période, etc.

        if view_mode == "global":
            # Colonnes dynamiques (g/d) selon le test
            col_g = getattr(TestResult, f"{global_test}_g")
            col_d = getattr(TestResult, f"{global_test}_d")

            # On récupère toutes les lignes où on a G et D
            rows = (
                db.session.query(TestResult.date_realisation, col_g, col_d)
                .filter(col_g.isnot(None), col_d.isnot(None))
                .order_by(TestResult.date_realisation.asc())
                .all()
            )

            # regroupe par date -> liste de déficits
            by_date = {}  # date -> [deficits...]
            for dt, g, d in rows:
                if g is None or d is None:
                    continue
                strong = max(g, d)
                weak = min(g, d)
                if strong is None or strong <= 0:
                    continue
                deficit = (1 - (weak / strong)) * 100

                by_date.setdefault(dt, []).append(deficit)

            # construit la série triée
            all_deficits = []
            for dt in sorted(by_date.keys()):
                vals = by_date[dt]
                if not vals:
                    continue
                avg = sum(vals) / len(vals)
                global_points.append(
                    {
                        "date": dt.strftime("%Y-%m-%d"),
                        "avg_deficit": round(avg, 1),
                        "n": len(vals),
                    }
                )
                all_deficits.extend(vals)

            if all_deficits:
                global_summary = {
                    "overall_avg": round(sum(all_deficits) / len(all_deficits), 1),
                    "n_total": len(all_deficits),
                }
            else:
                global_summary = {"overall_avg": None, "n_total": 0}

        return render_template(
            "analytics.html",
            # commun
            view_mode=view_mode,
            agents=agents,
            tests=tests,
            # individuel
            selected_agent=selected_agent,
            selected_test=selected_test,
            test_label=test_label,
            points=points,
            # global
            global_test=global_test,
            global_label=global_label,
            global_points=global_points,
            global_summary=global_summary,
        )

    @app.route("/agents/<int:agent_id>/results/new", methods=["POST"])
    @login_required
    def result_new(agent_id):
        agent = Firefighter.query.get_or_404(agent_id)

        date_str = request.form.get("date_realisation", "").strip()
        try:
            date_val = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            flash("Date invalide. Format attendu : YYYY-MM-DD", "danger")
            return redirect(url_for("agent_detail", agent_id=agent.id))

        def fnum(name: str):
            v = request.form.get(name, "").strip()
            if v == "":
                return None
            try:
                return float(v.replace(",", "."))
            except ValueError:
                return None

        r = TestResult(
            firefighter_id=agent.id,
            date_realisation=date_val,
            assis_debout_g=fnum("assis_debout_g"),
            assis_debout_d=fnum("assis_debout_d"),
            heel_raise_g=fnum("heel_raise_g"),
            heel_raise_d=fnum("heel_raise_d"),
            side_hop_g=fnum("side_hop_g"),
            side_hop_d=fnum("side_hop_d"),
            wall_test_g=fnum("wall_test_g"),
            wall_test_d=fnum("wall_test_d"),
        )

        db.session.add(r)
        db.session.commit()
        flash("Résultat ajouté.", "success")
        return redirect(url_for("agent_detail", agent_id=agent.id))

    @app.route("/results/<int:result_id>/delete", methods=["POST"])
    @login_required
    def result_delete(result_id):
        r = TestResult.query.get_or_404(result_id)
        agent_id = r.firefighter_id
        db.session.delete(r)
        db.session.commit()
        flash("Résultat supprimé.", "warning")
        return redirect(url_for("agent_detail", agent_id=agent_id))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
