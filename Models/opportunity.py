from .alchemy import db, commit
from Data import link
from .models import OddModel

class Opportunity(db.Model):
    __tablename__ = 'opportunity'
    id = db.Column(db.Integer, primary_key=True)
    sportsbook_id = db.Column(db.Integer, db.ForeignKey('sportsbook.id'), nullable=False)
    opp_description = db.Column(db.String(50), nullable=False)
    tip_type = db.Column(db.String(3))
    opp_number = db.Column(db.String(10))
    market_id = db.Column(db.String(10))
    bet_order = db.Column(db.Integer)
    sport_id = db.Column(db.Integer, db.ForeignKey('sport.id'), nullable=False)

    sport = db.relationship('Sport', uselist=False)
    sports_book = db.relationship('Sportsbook', uselist=False)

    def __repr__(self):
        return f"<Opportunity {self.opp_description}>" 
    
    @staticmethod
    def populate():
        all_ops, all_links = link()
        opportunities = []
        links = []
        opportunities.extend(Opportunity(**obj) for obj in all_ops)
        links.extend(OpportunityLink(**obj) for obj in all_links)
        db.session.add_all(opportunities)
        db.session.add_all(links)
        commit()  

    @staticmethod
    def get_relevant_opportunity(odd: OddModel, sport_id: int, sportsbook_id: int) -> OddModel:
        query = db.session.query(Opportunity).filter_by(
            sportsbook_id=sportsbook_id, 
            sport_id=sport_id, 
            tip_type = odd.tip_type,
            opp_number = odd.opp_number,
            market_id = odd.market_id,
            bet_order = odd.bet_order,
            )
        
        if sportsbook_id != 5: 
            query = query.filter_by(
                opp_description = odd.opp_description
            )

        opportunity = query.first()

        if opportunity:
            odd.opportunity_id = opportunity.id
            return odd     
        return None

class OpportunityLink(db.Model): 
    __tablename__ = 'opportunitylink'
    id = db.Column(db.Integer, primary_key=True)
    first_opportunity_id = db.Column(db.Integer, db.ForeignKey('opportunity.id'), nullable=False)
    second_opportunity_id = db.Column(db.Integer, db.ForeignKey('opportunity.id'), nullable=False)

    first_opportunity = db.relationship('Opportunity', uselist=False, foreign_keys=[first_opportunity_id])
    second_opportunity = db.relationship('Opportunity', uselist=False, foreign_keys=[second_opportunity_id])