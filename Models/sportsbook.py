from .alchemy import db

class Sportsbook(db.Model):
    __tablename__ = 'sportsbook'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    selected = db.Column(db.Boolean, default=False)
    tenis_url = db.Column(db.String(50), nullable=False)
    darts_url = db.Column(db.String(50), nullable=False)
    cricket_url = db.Column(db.String(50), nullable=False)
    baseball_url = db.Column(db.String(50), nullable=False)
    table_tennis_url = db.Column(db.String(50), nullable=False)
    snooker_url = db.Column(db.String(50), nullable=False)
    volleyball_url = db.Column(db.String(50), nullable=False)
    football_url = db.Column(db.String(50), nullable=False)
    hockey_url = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f"<Sportsbook {self.name}>"
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, Sportsbook):
            return False
        return self.id == other.id
