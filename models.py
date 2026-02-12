from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Firefighter(db.Model):
    __tablename__ = "firefighters"
    id = db.Column(db.Integer, primary_key=True)
    matricule = db.Column(db.String(50), nullable=True)
    nom = db.Column(db.String(80), nullable=False)
    prenom = db.Column(db.String(80), nullable=False)
    grade = db.Column(db.String(80), nullable=True)
    caserne = db.Column(db.String(120), nullable=True)

    results = db.relationship(
        "TestResult", backref="firefighter", cascade="all, delete-orphan"
    )


class TestResult(db.Model):
    __tablename__ = "test_results"
    id = db.Column(db.Integer, primary_key=True)
    firefighter_id = db.Column(
        db.Integer, db.ForeignKey("firefighters.id"), nullable=False
    )

    date_realisation = db.Column(db.Date, nullable=False)

    assis_debout_g = db.Column(db.Float, nullable=True)
    assis_debout_d = db.Column(db.Float, nullable=True)

    heel_raise_g = db.Column(db.Float, nullable=True)
    heel_raise_d = db.Column(db.Float, nullable=True)

    side_hop_g = db.Column(db.Float, nullable=True)
    side_hop_d = db.Column(db.Float, nullable=True)

    wall_test = db.Column(db.Float, nullable=True)
