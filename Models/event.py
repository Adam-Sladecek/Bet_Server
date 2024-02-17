from .alchemy import db, commit
from sqlalchemy import and_, or_
from datetime import timedelta
from .models import EventModel
from .sportsbook import Sportsbook
from fuzzywuzzy import fuzz
from Logging import configure_logging, logger

configure_logging()

class Event(db.Model): 
    __tablename__ = 'event'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, nullable=False)
    sportsbook_id = db.Column(db.Integer, db.ForeignKey('sportsbook.id'), nullable=False)
    date_time = db.Column(db.DateTime, nullable=False)
    first_name = db.Column(db.String(30), nullable=False)
    second_name = db.Column(db.String(50), nullable=False)
    sport_id = db.Column(db.Integer, db.ForeignKey('sport.id'), nullable=False)
    odds = db.relationship('Odd', backref='event', primaryjoin="and_(Event.event_id == Odd.event_id, Event.sportsbook_id == Odd.sportsbook_id)")
    sport = db.relationship('Sport', uselist=False)
    sportsbook = db.relationship('Sportsbook', uselist=False)

    @staticmethod
    def link_all_events(sport_id: int):
        events_to_be_linked = db.session.query(EventToBeLinked).filter(
            EventToBeLinked.sport_id == sport_id
        ).all()

        for obj in events_to_be_linked:
            event = obj.event
            sportsbook_id = obj.sportsbook_id
            success, matching_object = event.link_event(sportsbook_id)
            if success: 
                db.session.delete(obj)
            if matching_object:
                db.session.delete(matching_object)
        
        commit()

    def link_event(self, sportsbook_id: int) -> bool:
        increment = timedelta(hours=1)
        potential_matches = ( db.session.query(Event)
            .filter(Event.sport_id == self.sport_id)
            .filter(Event.sportsbook_id == sportsbook_id)
            .filter(Event.event_id != self.event_id)
            .filter(and_(Event.date_time <= self.date_time + increment, Event.date_time >= self.date_time - increment))
            .all() 
        ) 
        best_score = 0
        best_event = None
        for match in potential_matches:
            score = (fuzz.token_sort_ratio(match.first_name.strip().lower(), self.first_name.strip().lower()) \
                    + fuzz.token_sort_ratio(match.second_name.strip().lower(), self.second_name.strip().lower())) / 2.0
            if score > best_score: 
                best_score = score
                best_event = match
            
        if best_event and best_score >= 70:
            linked_event_id = best_event.id
            link_exists  = (
                db.session.query(EventLink)
                .filter(
                    or_(
                        and_(EventLink.first_event_id == self.id, EventLink.second_event_id == linked_event_id),
                        and_(EventLink.first_event_id == linked_event_id, EventLink.second_event_id == self.id)
                    )
                )
                .first()
            )
            if not link_exists:
                event_link = EventLink(
                    first_event_id=self.id,
                    second_event_id=linked_event_id
                )
                db.session.add(event_link)
                matching_object = db.session.query(EventToBeLinked).filter(
                    EventToBeLinked.event_id == linked_event_id,
                    EventToBeLinked.sportsbook_id == self.sportsbook_id,
                    EventToBeLinked.sport_id == self.sport_id
                ).first()
                if matching_object:
                    return True, matching_object
                logger.warning(f'Matching object for event {self.id} with id {linked_event_id} was not found.') 
                return True, None
        return False, None
    
    @staticmethod
    def update_events(events_list: list[EventModel], sport_id: int, sportsbook_id: int):
        sports_books = db.session.query(Sportsbook).all()
        existing_events = db.session.query(Event).filter_by(sport_id=sport_id, sportsbook_id=sportsbook_id).all()
        existing_events_dict = {event.event_id: event for event in existing_events}
        for event_data in events_list:
            if event_data.event_id in existing_events_dict:
                existing_event = existing_events_dict[event_data.event_id]
                existing_event.date_time = event_data.date_time
                continue
            new_event = Event(
                sport_id = event_data.sport_id,
                sportsbook_id = event_data.sportsbook_id,
                event_id = event_data.event_id,
                date_time = event_data.date_time,
                first_name = event_data.first_name,
                second_name = event_data.second_name,
            )
            db.session.add(new_event)
            db.session.commit()
            for sportsbook in sports_books: 
                if sportsbook.id == sportsbook_id: continue
                db.session.add(EventToBeLinked(event_id = new_event.id, sportsbook_id = sportsbook.id, sport_id = sport_id))
        used_event_ids = [event_data.event_id for event_data in events_list]
        for existing_event in existing_events:
            if existing_event.event_id not in used_event_ids:
                db.session.delete(existing_event)

        commit()

class EventLink(db.Model): 
    __tablename__ = 'eventlink'
    id = db.Column(db.Integer, primary_key=True)
    first_event_id = db.Column(db.Integer, db.ForeignKey('event.id', ondelete='CASCADE'), nullable=False)
    second_event_id = db.Column(db.Integer, db.ForeignKey('event.id', ondelete='CASCADE'), nullable=False)

    first_event = db.relationship('Event', uselist=False, foreign_keys=[first_event_id])
    second_event = db.relationship('Event', uselist=False, foreign_keys=[second_event_id])

class EventToBeLinked(db.Model): 
    __tablename__ = 'eventtobelinked'
    id = db.Column(db.Integer, primary_key=True)
    sport_id = db.Column(db.Integer, nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id', ondelete='CASCADE'), nullable=False)
    sportsbook_id = db.Column(db.Integer, db.ForeignKey('sportsbook.id'), nullable=False)

    event = db.relationship('Event', uselist=False)
    sportsbook = db.relationship('Sportsbook', uselist=False)