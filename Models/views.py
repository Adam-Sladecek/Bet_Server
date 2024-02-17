from flask_admin.contrib.sqla import ModelView

class SportsbookView(ModelView):
    column_display_pk = True  

class SporttypeView(ModelView):
    column_display_pk = True  

class SportView(ModelView):
    column_display_pk = True  
    column_list = ['id', 'name', 'sport_type_id']        

class OpportunityView(ModelView):
    column_display_pk = True 
    column_list = ['id', 'sport_id', 'sportsbook_id', 'opp_description', 'tip_type', 'opp_number', 'market_id', 'bet_order']

class OpportunityLinkView(ModelView):
    column_display_pk = True  
    column_list = ['id', 'first_opportunity_id', 'second_opportunity_id']

class EventView(ModelView):
    column_display_pk = True  

class EventLinkView(ModelView):
    column_display_pk = True  
    column_list = ['id', 'first_event_id', 'second_event_id']

class EventToBeLinkedView(ModelView):
    column_display_pk = True  
    column_list = ['id', 'sport_id', 'event_id', 'sportsbook_id']    
    
class OddView(ModelView):
    column_display_pk = True  

class ArbitragebetView(ModelView):
    column_display_pk = True  
    column_list = ['id', 'sport_name', 'profit']    

class ArbitragebetDetailView(ModelView):
    column_display_pk = True  
    column_list = ['id', 'arbitragebet_id', 'player_name', 'sportsbook_name', 'opportunity_name', 'odd', 'ammount']    