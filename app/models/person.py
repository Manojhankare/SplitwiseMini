from app.extensions import db


def normalize_name(name):
    return str(name).strip().lower()


class Person(db.Model):
    __tablename__ = "people"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, unique=True, nullable=False)

    def to_dict(self):
        return {"id": self.id, "name": self.name}

    @classmethod
    def list_all(cls):
        rows = cls.query.order_by(cls.name).all()
        return [r.to_dict() for r in rows]

    @classmethod
    def add(cls, name):
        name = normalize_name(name)
        if not name:
            return None
        existing = cls.query.filter_by(name=name).first()
        if existing:
            return existing
        person = cls(name=name)
        db.session.add(person)
        db.session.commit()
        return person

    @classmethod
    def register_names(cls, *names):
        for name in names:
            cls.add(name)

    @classmethod
    def delete(cls, person_id):
        person = db.session.get(cls, person_id)
        if person:
            db.session.delete(person)
            db.session.commit()
