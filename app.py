from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_socketio import SocketIO, emit
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from fuzzywuzzy import fuzz
import json 
from Data.link import link
from sqlalchemy.exc import IntegrityError
from models import EventModel
from sqlalchemy import and_, or_

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database2.db'  # Use your preferred database
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'your_jwt_secret_key'  # Change this to a secure key
app.config['SECRET_KEY'] = 'your_secret_key'  # Change this to a secure key for SocketIO

db = SQLAlchemy(app)
migrate = Migrate(app, db, render_as_batch=True)
socketio = SocketIO(app, cors_allowed_origins="*")
admin = Admin(app, name='Admin', template_mode='bootstrap3')

class Sportsbook(db.Model):
    __tablename__ = 'sportsbook'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
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

class SportsbookView(ModelView):
    column_display_pk = True  

admin.add_view(SportsbookView(Sportsbook, db.session))

class Sporttype(db.Model):
    __tablename__ = 'sporttype'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True, nullable=False)

    def __repr__(self):
        return f"<Sporttype {self.name}>"

class SporttypeView(ModelView):
    column_display_pk = True  

admin.add_view(SporttypeView(Sporttype, db.session))

class Sport(db.Model):
    __tablename__ = 'sport'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True, nullable=False)
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

class SportView(ModelView):
    column_display_pk = True  
    column_list = ['id', 'name', 'sport_type_id'] 
admin.add_view(SportView(Sport, db.session))

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

class OpportunityView(ModelView):
    column_display_pk = True 
    column_list = ['id', 'sport_id', 'sportsbook_id', 'opp_description', 'tip_type', 'opp_number', 'market_id', 'bet_order']

admin.add_view(OpportunityView(Opportunity, db.session))

class OpportunityLink(db.Model): 
    __tablename__ = 'opportunitylink'
    id = db.Column(db.Integer, primary_key=True)
    first_opportunity_id = db.Column(db.Integer, db.ForeignKey('opportunity.id'), nullable=False)
    second_opportunity_id = db.Column(db.Integer, db.ForeignKey('opportunity.id'), nullable=False)

    first_opportunity = db.relationship('Opportunity', uselist=False, foreign_keys=[first_opportunity_id])
    second_opportunity = db.relationship('Opportunity', uselist=False, foreign_keys=[second_opportunity_id])

class OpportunityLinkView(ModelView):
    column_display_pk = True  

admin.add_view(OpportunityLinkView(OpportunityLink, db.session))

class Event(db.Model): 
    __tablename__ = 'event'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, nullable=False)
    sportsbook_id = db.Column(db.Integer, db.ForeignKey('sportsbook.id'), nullable=False)
    date_time = db.Column(db.DateTime, nullable=False)
    first_name = db.Column(db.String(30), nullable=False)
    second_name = db.Column(db.String(50), nullable=False)
    sport_id = db.Column(db.Integer, db.ForeignKey('sport.id'), nullable=False)
    odds = db.relationship('Odd', primaryjoin="and_(Event.event_id == Odd.event_id, Event.sportsbook_id == Odd.sportsbook_id)")
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
            if event.link_event(sportsbook_id): 
                db.session.delete(obj)
        
        commit()

    def link_event(self, sportsbook_id: int) -> bool:
        best_event = ( db.session.query(
                Event.event_id.label('event_id'),
                (fuzz.token_sort_ratio(Event.first_name, self.first_name) +
                 fuzz.token_sort_ratio(Event.second_name, self.second_name)) / 2.0
                 .label('total_token_sort_ratio')
            )
            .filter(Event.sport_id == self.sport_id)
            .filter(Event.sportsbook_id == sportsbook_id)
            .filter(abs((Event.date_time - self.date_time).total_seconds()) <= 3600)
            .order_by('total_token_sort_ratio desc')
            .first() ) 
        
        if best_event and best_event.total_token_sort_ratio >= 70:
            linked_event_id = best_event.event_id
            existing_link = (
                db.session.query(EventLink)
                .filter(
                    or_(
                        and_(EventLink.first_event_id == self.event_id, EventLink.second_event_id == linked_event_id),
                        and_(EventLink.first_event_id == linked_event_id, EventLink.second_event_id == self.event_id)
                    )
                )
                .first()
            )
            if not existing_link:
                event_link = EventLink(
                    first_event_id=self.event_id,
                    second_event_id=linked_event_id
                )
                db.session.add(event_link)
                return True
        return False
    
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
                sport_id = sport_id,
                sportsbook_id = sportsbook_id,
                event_id = event_data.event_id,
                date_time = event_data.date_time,
                first_name = event_data.first_name,
                second_name = event_data.second_name,
            )
            db.session.add(new_event)
            for sports_book in sports_books: 
                if sports_book.id == sportsbook_id: continue
                db.session.add(EventToBeLinked(event_id = event_data.event_id, sportsbook_id = sports_book.id, sport_id = sport_id))

        used_event_ids = [event_data.event_id for event_data in events_list]
        for existing_event in existing_events:
            if existing_event.event_id not in used_event_ids:
                db.session.delete(existing_event)

        commit()

class EventView(ModelView):
    column_display_pk = True  

admin.add_view(EventView(Event, db.session))

class EventLink(db.Model): 
    __tablename__ = 'eventlink'
    id = db.Column(db.Integer, primary_key=True)
    first_event_id = db.Column(db.Integer, db.ForeignKey('event.id', ondelete='CASCADE'), nullable=False)
    second_event_id = db.Column(db.Integer, db.ForeignKey('event.id', ondelete='CASCADE'), nullable=False)

    first_event = db.relationship('Event', uselist=False, foreign_keys=[first_event_id])
    second_event = db.relationship('Event', uselist=False, foreign_keys=[second_event_id])

class EventLinkView(ModelView):
    column_display_pk = True  

admin.add_view(EventLinkView(EventLink, db.session))

class EventToBeLinked(db.Model): 
    __tablename__ = 'eventtobelinked'
    id = db.Column(db.Integer, primary_key=True)
    sport_id = db.Column(db.Integer, nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id', ondelete='CASCADE'), nullable=False)
    sportsbook_id = db.Column(db.Integer, db.ForeignKey('sportsbook.id'), nullable=False)

    event = db.relationship('Event', uselist=False)
    sportsbook = db.relationship('Sportsbook', uselist=False)

class EventToBeLinkedView(ModelView):
    column_display_pk = True  

admin.add_view(EventToBeLinkedView(EventToBeLinked, db.session))

class Odd(db.Model): 
    __tablename__ = 'odd'
    id = db.Column(db.Integer, primary_key=True)
    bet_id = db.Column(db.Integer, nullable=False)
    odd = db.Column(db.Numeric(precision=6, scale=2), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.event_id', ondelete='CASCADE'), nullable=False)
    sportsbook_id = db.Column(db.Integer, db.ForeignKey('event.sportsbook_id'), nullable=False)
    opportunity_id = db.Column(db.Integer, db.ForeignKey('opportunity.id'), nullable=False)
    opportunity = db.relationship('Opportunity', uselist=False)

class OddView(ModelView):
    column_display_pk = True  

admin.add_view(OddView(Odd, db.session))

@app.route('/update_events', methods=['POST'])
def update_events():
    pass

@app.route('/update_odds', methods=['POST'])
def update_odds():
    pass

def commit():
    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        print(f"Error: {str(e)}")


# SocketIO event example
@socketio.on('message')
def handle_message(data):
    emit('message_response', data)

@app.route('/get_all_sportsbooks' , methods=['GET'])
def get_all_sportsbooks():
    opps = Opportunity.query.all()
    opportunity_data = []
    for opp in opps:
        if opp.nike_opportunity_id is not None and opp.nike_opportunity_id > 0: 
            opportunity_data.append({
                "id": opp.id,
                "opp_description": opp.opp_description,
                "nike_link": opp.nike_opportunity_id,
                "doxxbet_link": opp.doxxbet_opportunity_id,
                "ifortuna_link": opp.ifortuna_opportunity_id,
                "tipsport_link": opp.tipsport_opportunity_id,
                "tipos_link": opp.tipos_opportunity_id,
                "betfair_link": opp.betfair_opportunity_id,
                "nike" : None if opp.nike_opportunity is None else opp.nike_opportunity.opp_description,
                "doxxbet" : None if opp.doxxbet_opportunity is None else opp.doxxbet_opportunity.opp_description
            })
    return jsonify({"opportunities": opportunity_data})

def add_events(): 
    events = [
        EventModel()
    ]

if __name__ == '__main__':
    # if len(sys.argv) > 1 and sys.argv[1] == '--populate':
    with app.app_context():
        db.drop_all()
        db.create_all()
        Sport.populate()
        Opportunity.populate()
    socketio.run(app, debug=True)
