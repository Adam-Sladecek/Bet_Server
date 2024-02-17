from .alchemy import db

class Arbitragebet(db.Model): 
    __tablename__ = 'arbitragebet'
    id = db.Column(db.Integer, primary_key=True)
    updated = db.Column(db.DateTime, nullable=False)
    first_odd_id = db.Column(db.Integer, nullable=False)
    second_odd_id = db.Column(db.Integer, nullable=False)
    sport_id = db.Column(db.Integer, nullable=False)
    sport_name = db.Column(db.String(20), nullable=False)
    profit = db.Column(db.Numeric(precision=6, scale=2), nullable=False)
    details = db.relationship('Arbitragebetdetail', backref='arbitragebet')

class Arbitragebetdetail(db.Model):
    __tablename__ = 'arbitragebetdetail'
    id = db.Column(db.Integer, primary_key=True)
    arbitragebet_id = db.Column(db.Integer, db.ForeignKey('arbitragebet.id', ondelete='CASCADE'), nullable=False)
    player_name = db.Column(db.String(30), nullable=False)
    sportsbook_name = db.Column(db.String(10), nullable=False)
    opportunity_name = db.Column(db.String(50), nullable=False)
    odd = db.Column(db.Numeric(precision=6, scale=2), nullable=False)
    ammount = db.Column(db.Numeric(precision=6, scale=2), nullable=False)

