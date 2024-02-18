from .alchemy import db, commit
from .sportsbook import Sportsbook
from .sporttype import Sporttype
import json

class Sport(db.Model):
    __tablename__ = 'sport'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True, nullable=False)
    selected = db.Column(db.Boolean, default=False)
    url = db.Column(db.String(20), nullable=False)
    sport_type_id = db.Column(db.Integer, db.ForeignKey('sporttype.id'), nullable=False)
    sport_type = db.relationship('Sporttype')

    def __repr__(self):
        return f"<Sport {self.name}>"      
    
    @staticmethod
    def populate():
        with open("Data/data.json", encoding="utf-8") as file:
            contents = file.read()
            data = json.loads(contents)
            sports_books = []
            sport_types = []
            sports = []
            sports_books.extend(Sportsbook(**obj) for obj in data["sports_books"])
            sports.extend(Sport(**obj) for obj in data["sports"])
            sport_types.extend(Sporttype(**obj) for obj in data["sport_types"])
            db.session.add_all(sports_books)
            db.session.add_all(sport_types)
            db.session.add_all(sports)
            commit()