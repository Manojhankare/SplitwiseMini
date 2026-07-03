from app.extensions import db

group_members = db.Table(
    "group_members",
    db.Column("group_id", db.Integer, db.ForeignKey("groups.id"), primary_key=True),
    db.Column("person_id", db.Integer, db.ForeignKey("people.id"), primary_key=True),
)


class Group(db.Model):
    __tablename__ = "groups"
    __table_args__ = (db.UniqueConstraint("user_id", "name", name="uq_user_group_name"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.Text, nullable=False)
    members = db.relationship("Person", secondary=group_members, lazy="joined")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "members": [m.to_dict() for m in self.members],
        }

    @classmethod
    def list_all(cls, user_id):
        rows = cls.query.filter_by(user_id=user_id).order_by(cls.name).all()
        return [r.to_dict() for r in rows]

    @classmethod
    def get_for_user(cls, group_id, user_id):
        return cls.query.filter_by(id=group_id, user_id=user_id).first()

    @classmethod
    def create(cls, user_id, name, member_ids):
        group = cls(user_id=user_id, name=name.strip())
        db.session.add(group)
        db.session.flush()
        cls._set_members(group, user_id, member_ids)
        db.session.commit()
        return group

    @classmethod
    def update(cls, group_id, user_id, name=None, member_ids=None):
        group = cls.get_for_user(group_id, user_id)
        if not group:
            return None
        if name is not None:
            group.name = name.strip()
        if member_ids is not None:
            cls._set_members(group, user_id, member_ids)
        db.session.commit()
        return group

    @classmethod
    def _set_members(cls, group, user_id, member_ids):
        from app.models.person import Person

        members = Person.query.filter(
            Person.id.in_(member_ids), Person.user_id == user_id
        ).all()
        group.members = members

    @classmethod
    def delete(cls, group_id, user_id):
        group = cls.get_for_user(group_id, user_id)
        if group:
            db.session.delete(group)
            db.session.commit()
