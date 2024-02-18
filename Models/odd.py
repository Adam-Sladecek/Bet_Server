from .alchemy import db, commit
from .opportunity import Opportunity, OpportunityLink
from .event import Event, EventLink
from Logging import configure_logging, logger
from .models import OddModel
import json 
from dataclasses import asdict
from sqlalchemy.orm import aliased
from sqlalchemy import and_, or_
from .arbitragebet import Arbitragebet, Arbitragebetdetail
from Utils import oddsToImpliedPB, getProfit, stakeForArbitrageBet
from datetime import datetime
from .sport import Sport

configure_logging()

class Odd(db.Model): 
    __tablename__ = 'odd'
    id = db.Column(db.Integer, primary_key=True)
    bet_id = db.Column(db.Integer, nullable=False)
    tip_type = db.Column(db.String(3))
    odd = db.Column(db.Numeric(precision=6, scale=2), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.event_id', ondelete='CASCADE'), nullable=False)
    sportsbook_id = db.Column(db.Integer, db.ForeignKey('event.sportsbook_id'), nullable=False)
    opportunity_id = db.Column(db.Integer, db.ForeignKey('opportunity.id'), nullable=False)
    opportunity = db.relationship('Opportunity', uselist=False)

    @staticmethod
    def update_odds(odd_dictionary: dict[int, list[OddModel]], sport_id: int, sportsbook_id: int):
        for event_id, odds in odd_dictionary.items():
            existing_odds = db.session.query(Odd).filter_by(sportsbook_id=sportsbook_id, event_id=event_id).all()
            existing_odds_dict = {(odd.bet_id, odd.tip_type): odd for odd in existing_odds}
            for odd in odds:
                if (odd.bet_id, odd.tip_type) in existing_odds_dict:
                    existing_odd = existing_odds_dict[odd.bet_id]
                    existing_odd.odd = odd.odd
                    continue
                result = Opportunity.get_relevant_opportunity(odd, sport_id, sportsbook_id)    
                if not result:
                    odd_dict = asdict(odd)
                    json_string = json.dumps(odd_dict, indent=2)
                    logger.warning(f'Opportunity for {json_string} was not found.') 
                    continue
                new_odd = Odd(
                    bet_id = result.bet_id,
                    tip_type = result.tip_type,
                    sportsbook_id = result.sportsbook_id,
                    event_id = result.event_id,
                    odd = result.odd,
                    opportunity_id = result.opportunity_id
                )
                db.session.add(new_odd)
        used_odd_ids = [(odd.bet_id, odd.tip_type) for odd in existing_odds]
        for existing_odd in existing_odds:
            if (existing_odd.bet_id, existing_odd.tip_type) not in used_odd_ids:
                db.session.delete(existing_odd)        
        commit()

    @classmethod
    def get_arbitrage_odds(cls, sport_id: int):
        odd_alias1 = aliased(cls)
        odd_alias2 = aliased(cls)
        event_alias1 = aliased(Event)
        event_alias2 = aliased(Event)

        all_linked_opportunity_odds_pairs = (
            db.session.query(odd_alias1, odd_alias2, event_alias1, event_alias2)
            .join(Event, and_(
                odd_alias1.event_id == Event.event_id,
                odd_alias1.sportsbook_id == Event.sportsbook_id))
            .join(Opportunity, odd_alias1.opportunity_id == Opportunity.id)
            .join(OpportunityLink, OpportunityLink.first_opportunity_id == Opportunity.id)
            .join(odd_alias2, OpportunityLink.second_opportunity_id == odd_alias2.opportunity_id)
            .join(EventLink, or_(
                and_(EventLink.first_event_id == event_alias1.id, EventLink.second_event_id == event_alias2.id),
                and_(EventLink.first_event_id == event_alias2.id, EventLink.second_event_id == event_alias1.id)
            ))
            .filter(event_alias1.sport_id == sport_id)
            .filter(odd_alias1.event_id == event_alias1.event_id)
            .filter(odd_alias2.event_id == event_alias2.event_id)
            .all()
        )   
        pairs_with_arbitrage = []
        for pair in all_linked_opportunity_odds_pairs:
            first_odd = pair[0]  
            second_odd = pair[1]
            has_arbitrage = 100/first_odd.odd + 100/second_odd.odd < 100
            if has_arbitrage:
                pairs_with_arbitrage.append((first_odd, second_odd))

        update_arbitrage_bets(pairs_with_arbitrage, sport_id)

    
def update_arbitrage_bets(odd_list: list[tuple[Odd, Odd]], sport_id: int):
    if len(odd_list) == 0:
        db.session.query(Arbitragebet).filter_by(sport_id=sport_id).delete()
        commit()  
        return
    sport = db.session.query(Sport).filter_by(id=sport_id).first()
    arbitrage_bets = db.session.query(Arbitragebet).filter_by(sport_id=sport_id).all()
    arbitrage_bets_dict = {(pair.first_odd_id, pair.second_odd_id): pair for pair in arbitrage_bets}
    for odd1, odd2 in odd_list: 
        if (odd1.id, odd2.id) in arbitrage_bets_dict:
            arbitrage_bet = arbitrage_bets_dict[(odd1.id, odd2.id)]
            arbitrage_bet.updated = datetime.now()
            details = arbitrage_bet.details
            details[0].odd = odd1.odd
            details[0].ammount = stakeForArbitrageBet(oddsToImpliedPB([odd1.odd]), oddsToImpliedPB([odd1.odd, odd2.odd]))
            details[1].odd = odd2.odd
            details[1].ammount = stakeForArbitrageBet(oddsToImpliedPB([odd2.odd]), oddsToImpliedPB([odd1.odd, odd2.odd]))
            continue
        new_bet = Arbitragebet(
            updated = datetime.now(),
            first_odd_id = odd1.id,
            second_odd_id = odd2.id,
            sport_id = sport.id,
            sport_name = sport.name, 
            profit = getProfit(oddsToImpliedPB([odd1.odd, odd2.odd]))
        )
        first_name = odd1.event.first_name
        second_name = odd2.event.second_name
        details = [
            Arbitragebetdetail(
                arbitragebet = new_bet, 
                player_name = first_name,
                sportsbook_name = odd1.event.sportsbook.name,
                opportunity_name = odd1.opportunity.opp_description.replace('*1*', first_name).replace('*2*', second_name),
                odd = odd1.odd,
                ammount = stakeForArbitrageBet(oddsToImpliedPB([odd1.odd]), oddsToImpliedPB([odd1.odd, odd2.odd]))
            ),
            Arbitragebetdetail(
                arbitragebet = new_bet, 
                player_name = second_name,
                sportsbook_name = odd2.event.sportsbook.name,
                opportunity_name = odd2.opportunity.opp_description.replace('*1*', first_name).replace('*2*', second_name),
                odd = odd2.odd,
                ammount = stakeForArbitrageBet(oddsToImpliedPB([odd2.odd]), oddsToImpliedPB([odd1.odd, odd2.odd]))
            )
        ]
        new_bet.details.extend(details)
        db.session.add(new_bet)
        db.session.add_all(details)

    used_pairs = [(odd1.id, odd2.id) for odd1, odd2 in odd_list]
    for arbitrage_bet in arbitrage_bets:
        if (arbitrage_bet.first_odd_id, arbitrage_bet.second_odd_id) not in used_pairs:
            db.session.delete(arbitrage_bet)
    commit()   
        