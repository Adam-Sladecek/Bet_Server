from .alchemy import db

class Sporttype(db.Model):
    __tablename__ = 'sporttype'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True, nullable=False)

    def __repr__(self):
        return f"<Sporttype {self.name}>"