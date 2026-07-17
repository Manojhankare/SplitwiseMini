from app.extensions import db


def normalize_name(name):
    return str(name).strip().lower()


class Person(db.Model):
    __tablename__ = "people"
    __table_args__ = (db.UniqueConstraint("user_id", "name", name="uq_user_person_name"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.Text, nullable=False)

    def to_dict(self):
        return {"id": self.id, "name": self.name}

    @classmethod
    def list_all(cls, user_id):
        rows = cls.query.filter_by(user_id=user_id).order_by(cls.name).all()
        return [r.to_dict() for r in rows]

    @classmethod
    def add(cls, user_id, name):
        name = normalize_name(name)
        if not name or name == "self":
            return None
        existing = cls.query.filter_by(user_id=user_id, name=name).first()
        if existing:
            return existing
        person = cls(user_id=user_id, name=name)
        db.session.add(person)
        db.session.commit()
        return person

    @classmethod
    def register_names(cls, user_id, *names):
        wanted = []
        seen = set()
        for raw in names:
            name = normalize_name(raw)
            if not name or name == "self" or name in seen:
                continue
            seen.add(name)
            wanted.append(name)
        if not wanted:
            return

        existing = {
            p.name
            for p in cls.query.filter(
                cls.user_id == user_id,
                cls.name.in_(wanted),
            ).all()
        }
        added = False
        for name in wanted:
            if name in existing:
                continue
            db.session.add(cls(user_id=user_id, name=name))
            added = True
        if added:
            db.session.commit()

    @classmethod
    def get_for_user(cls, person_id, user_id):
        return cls.query.filter_by(id=person_id, user_id=user_id).first()

    @classmethod
    def delete(cls, person_id, user_id):
        person = cls.get_for_user(person_id, user_id)
        if person:
            db.session.delete(person)
            db.session.commit()
