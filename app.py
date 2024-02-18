from flask import Flask, jsonify, request
from flask_migrate import Migrate
from flask_socketio import SocketIO, emit
from flask_admin import Admin
from Models import *
from datetime import datetime, timedelta
from Logging import configure_logging, logger
import threading
from Scrapes import scrape

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database2.db'  # Use your preferred database
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'your_jwt_secret_key'  # Change this to a secure key
app.config['SECRET_KEY'] = 'your_secret_key'  # Change this to a secure key for SocketIO
db.init_app(app)

configure_logging()

migrate = Migrate(app, db, render_as_batch=True)
socketio = SocketIO(app, cors_allowed_origins="*")
admin = Admin(app, name='Admin', template_mode='bootstrap3')

admin.add_view(SportsbookView(Sportsbook, db.session))
admin.add_view(SporttypeView(Sporttype, db.session))
admin.add_view(SportView(Sport, db.session))
admin.add_view(OpportunityView(Opportunity, db.session))
admin.add_view(OpportunityLinkView(OpportunityLink, db.session))
admin.add_view(EventView(Event, db.session))
admin.add_view(EventLinkView(EventLink, db.session))
admin.add_view(EventToBeLinkedView(EventToBeLinked, db.session))
admin.add_view(OddView(Odd, db.session))
admin.add_view(ArbitragebetView(Arbitragebet, db.session))
admin.add_view(ArbitragebetDetailView(Arbitragebetdetail, db.session))

# @app.route('/events', methods=['POST'])
# def update_events():
#     try:
#         json_data = request.get_json()
#         sport_id = json_data['sport_id']
#         sportsbook_id = json_data['sportsbook_id']
#         events = [EventModel(**event_data) for event_data in json_data['events']]
#         Event.update_events(events, sport_id, sportsbook_id)
#         return jsonify({'message': 'Events updated.'}), 200
    
#     except Exception as e:
#         logger.error(str(e)) 
#         return jsonify({'error': str(e)}), 400

# @app.route('/odds', methods=['POST'])
# def update_odds():
#     try:
#         json_data = request.get_json()
#         sport_id = json_data['sport_id']
#         sportsbook_id = json_data['sportsbook_id']
#         odd_dictionary = {key: [OddModel(**odd_data) for odd_data in odds_list] for key, odds_list in json_data['odds_dict'].items()}
#         Odd.update_odds(odd_dictionary, sport_id, sportsbook_id)
#         return jsonify({'message': 'Odds updated.'}), 200
    
#     except Exception as e:
#         logger.error(str(e))
#         return jsonify({'error': str(e)}), 400
    
scrape_task_running = False
scrape_event = None
scrape_thread = None

@app.route('/start', methods=['GET']) # socket
async def start_scrape():
    try:
        print("Starting scrape.")  
        sportsbooks = db.Query(Sportsbook).filter_by(selected=True).all()
        sports = db.Query(Sport).filter_by(selected=True).all()
        global scrape_task_running, scrape_thread, scrape_event
        if not scrape_task_running:
            scrape_event = threading.Event()
            number_of_drivers = 5
            scrape_thread = threading.Thread(target=scrape, args=(sportsbooks, sports, scrape_event, number_of_drivers))
            scrape_thread.start()
        print("Scrape started.")      
        return jsonify({'started': True}) , 200
    
    except Exception as e:
        logger.error(str(e))
        return jsonify({'error': str(e)}), 400

@app.route('/end', methods=['GET']) # socket
def end_scrape():
    try:
        print("Ending scrape.")  
        global scrape_task_running, scrape_event, scrape_thread, ending_scrape
        if scrape_task_running:
            ending_scrape = True
            scrape_event.set()
            scrape_thread.join()
        ending_scrape = False 
        return jsonify({'ended': True}), 200
    
    except Exception as e:
        logger.error(str(e))
        return jsonify({'error': str(e)}), 400
    
@app.route('/sportsbooks', methods=['GET']) # socket
def get_sportsbooks_with_urls():
    try:
        
        return jsonify([{'ended': True}]), 200
    
    except Exception as e:
        logger.error(str(e))
        return jsonify({'error': str(e)}), 400    

# # SocketIO event example
# @socketio.on('message')
# def handle_message(data):
#     emit('message_response', data)

def add_events(): 
    db.session.query(Event).delete()
    db.session.query(EventToBeLinked).delete()
    db.session.query(EventLink).delete()
    db.session.query(Odd).delete()
    commit()
    events_nike = [
        EventModel(2232, 3, 2, datetime.now(), "jozko mrkvicka", "mirko dragic"),
        EventModel(2242, 3, 2, datetime.now(), "pow55w", "ooqkkdkeew")
    ]
    increment = timedelta(hours=2)
    events_dx = [
        EventModel(66558, 6, 2, datetime.now(), "fsdfsf", "fsdfsdf"),
        EventModel(55698, 6, 2, datetime.now(), "pow55w", "ooqkkdkeew"),
        EventModel(4415, 6, 2, datetime.now(), "j. mrkvicka", "m. dragic"),
        EventModel(77899, 6, 2, datetime.now(), "c cmzcka", "asdada5 l"),
        EventModel(77789, 6, 2, datetime.now(), "dadkoo", "dalloloaksd")
    ]
    events_tipsport = [
        EventModel(789874, 4, 2, datetime.now(), "mrkvicka jozko", "dragic mirko")
    ]
    Event.update_events(events_nike, 2, 3)
    Event.update_events(events_dx, 2, 6)
    Event.update_events(events_tipsport, 2, 4)
    Event.link_all_events(2)

    odds_nike = {
        2232: [
            OddModel(12345, 2.1, 2232, 3, "2560", "Víťaz zápasu *1*", "49", None, 0, None),
            OddModel(12346, 1.8, 2232, 3, "2560", "Víťaz zápasu *2*", "50", None, 0, None)
        ],
        2242: [
            OddModel(4564, 2.1, 2242, 3, "2560", "Víťaz zápasu *1*", "49", None, 0, None),
            OddModel(77789, 1.1, 2242, 3, "2560", "Víťaz zápasu *2*", "50", None, 0, None)
        ]
    }
    odds_dx = {
        4415: [
            OddModel(14415, 2, 4415, 6, None, "Výsledok *2*", "2", None, None, None),
            OddModel(144115, 5, 4415, 6, None, "Výsledok *1*", "1", None, None, None),
            ],
        55698: [
            OddModel(147715, 2, 55698, 6, None, "Výsledok *2*", "2", None, None, None),
            ]    
    }
    Odd.update_odds(odds_nike, 2, 3)
    Odd.update_odds(odds_dx, 2, 6)
    Odd.get_arbitrage_odds(2)

if __name__ == '__main__':
    # if len(sys.argv) > 1 and sys.argv[1] == '--populate':
    with open('app.log', 'w'):
        pass
    with app.app_context():
        db.drop_all()
        db.create_all()
        Sport.populate()
        Opportunity.populate()
        add_events()
    socketio.run(app, debug=True)

# TODO: each odd should have unique opportunity
# TODO: add scraping logic    
# TODO: add tests    