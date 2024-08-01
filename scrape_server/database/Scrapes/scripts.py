import asyncio
from enum import Enum
import logging
from fuzzywuzzy import fuzz
from .dataclass_models import EventModel, OddModel, MatchResponse
# from Utils import odds_to_implied_pb, get_profit, stake_for_arbitrage_bet
from database.models import Sportsbook, Sport, Opportunity, Odd, Event
from django.db import transaction
from django.db.models import Q, F, Value, FloatField, ExpressionWrapper, Sum
import pytz
from collections import defaultdict
from ..enums import DataType, TaskState, Movement
from channels.layers import get_channel_layer

def update_events(events_list: list[EventModel], sportsbook: Sportsbook):
    existing_events = Event.objects.select_related('sportsbook').filter(sportsbook=sportsbook).all()
    existing_events_dict = {event.event_id: event for event in existing_events}
    new_events = []
    events_to_update = []
    for event_data in events_list:
        if event_data.event_id in existing_events_dict:
            existing_event = existing_events_dict[event_data.event_id]
            existing_event.time = event_data.time
            events_to_update.append(existing_event)
            continue
        
        new_event = Event(
            event_id=event_data.event_id,
            time= event_data.time,
            home = event_data.home,
            away = event_data.away,
            is_default=sportsbook.is_default,
            selected=event_data.selected,
            sportsbook_id=event_data.sportsbook_id,
            sport_id=event_data.sport_id
        )
        new_events.append(new_event)

    with transaction.atomic():
        used_event_ids = [event_data.event_id for event_data in events_list]
        Event.objects.filter(sportsbook=sportsbook).exclude(event_id__in=used_event_ids).delete()
        Event.objects.bulk_update(events_to_update, ['time'])
        Event.objects.bulk_create(new_events)

def update_selected_events(events_to_update: list[Event], events_to_delete: list[Event]):
    with transaction.atomic():
        for event in events_to_delete: 
            event.delete()
        Event.objects.bulk_update(events_to_update, ['time'])

def update_odds(odds_to_create: list[OddModel], odds_to_update: list[Odd], sportsbook: Sportsbook):
    # logger = logging.getLogger('django')
    events = Event.objects.select_related('sport').filter(sportsbook=sportsbook, event_id__in=[odd.event_id for odd in odds_to_create]).all()
    events_dict = {event.event_id: event for event in events}

    update_selected_odds(odds_to_update)

    new_odds = []
    new_opportunities: list[Opportunity] = []
    opportunities_dict = get_relevant_opportunities(odds_to_create, sportsbook)

    for odd in odds_to_create:
        event = events_dict[odd.event_id]
        if odd.description in opportunities_dict: 
            opportunity = opportunities_dict[odd.description]
            new_odd = Odd(
                odd_id=odd.odd_id,
                code=odd.code,
                movement=odd.movement,
                odd=odd.odd,
                is_default=event.is_default,
                selected=False,
                locked=odd.locked,
                event=event,
                sportsbook=sportsbook,
                opportunity=opportunity
            )
            new_odds.append(new_odd)
            continue
        if odd.description in [opp.description for opp in new_opportunities]: continue
        new_opp = Opportunity(
            description=odd.description,
            is_default=event.is_default,
            sportsbook=sportsbook, 
            sport=event.sport,
            market_id=odd.market_id
        )
        new_opportunities.append(new_opp)
        
    with transaction.atomic():
        Opportunity.objects.bulk_create(new_opportunities)
        Odd.objects.bulk_create(new_odds)

def update_selected_odds(odds_to_update: list[Odd]):
    with transaction.atomic():
        Odd.objects.bulk_update(odds_to_update, ['odd', 'locked', 'movement'])

def get_existing_odds(sportsbook: Sportsbook, include_code: bool=False):
    events = Event.objects.filter(sportsbook=sportsbook).prefetch_related('odds').all()
    if include_code:
        return {event.event_id: {(odd.odd_id, odd.code): odd for odd in event.odds.all()} for event in events}
    return {event.event_id: {odd.odd_id: odd for odd in event.odds.all()} for event in events}

def get_selected_events(sportsbook: Sportsbook) -> tuple[list[Event], set]:
    default_events = Event.objects.filter(is_default=True, selected=True, sportsbook=sportsbook).select_related('sport').prefetch_related(
        'odds',
        'children', 
        'children__sportsbook',
        'children__odds',
        'children__sport'
    ).all()

    result: list[Event] = []
    sport_ids = set()
    for event in default_events: 
        ev = event if sportsbook.is_default else event.children.first(sportsbook=sportsbook)
        if ev is None: continue
        result.append(ev)
        sport_ids.add(ev.sport.pk)

    return result, sport_ids

def get_relevant_opportunities(odds: list[OddModel], sportsbook: Sportsbook) -> dict[tuple[int, str], Opportunity]:
    conditions = Q(sportsbook_id=sportsbook.pk)
    conditions &= Q(description__in=[odd.description for odd in odds])
    relevant_opportunities = Opportunity.objects.filter(conditions).all()
    opportunities_dict = {
        opportunity.description: opportunity for opportunity in relevant_opportunities
    }

    return opportunities_dict

def send_updated_events():
    sportsbook = Sportsbook.objects.filter(is_default=True, selected=True).first()
    events, _ = get_selected_events(sportsbook)
    response = MatchResponse.dataclass_from_models(events, Sportsbook.objects.filter(selected=True).all())
    asyncio.run(broadcast_data(DataType.MATCHDATA, response.dict))

def clear_unused_events():
    unused_sportsbooks = Sportsbook.objects.filter(selected=False).all()
    sb_ids = [sb.pk for sb in unused_sportsbooks]

    with transaction.atomic():
        Event.objects.filter(sportsbook_id__in=sb_ids).delete()

def link_all_events():
    parents = Event.objects.filter(is_default=True).select_related(
        'sport',
    ).prefetch_related(
        'children',
        'children__sportsbook',
        'children__sport',
    ).all()

    parents_by_sport = defaultdict(list[Event])
    for parent in parents: 
        parents_by_sport[parent.sport.pk].append(parent)

    events = Event.objects.filter(is_default=False).select_related(
        'sportsbook',
        'sport',
        'parent',
    ).all()

    events_to_link = [event for event in events if not event.has_parent]
    events_to_update = []
    events_by_parent = defaultdict(list[Event])
    for event in events_to_link: 
        best_match, events_by_parent = find_best_parent(event, parents_by_sport[event.sport.pk], events_by_parent)
        if best_match is not None: 
            event.add_parent(best_match)
            events_to_update.append(event)
    
    with transaction.atomic():
        Event.objects.bulk_update(events_to_update, ['parent'])

def find_best_parent(event_to_be_linked: Event, parents: list[Event], events_by_parent: dict[int, list[Event]]) -> Event:
    best_score = 0
    best_parent = None
    for parent in parents:
        score = (fuzz.token_sort_ratio(parent.home.lower(), event_to_be_linked.home.lower()) +
                    fuzz.token_sort_ratio(parent.away.lower(), event_to_be_linked.away.lower())) / 2.0
        if score > best_score:
            best_score = score
            best_parent = parent
    
    if best_parent and best_score >= 70:
        potential_link_indices = [index for index, link in enumerate(event_links) if link.is_potential_link(best_event, event_to_be_linked)]
        if len(potential_link_indices) == 1: 
            link_index = potential_link_indices[0]
            if event_links[link_index].score < best_score: 
                event_links[link_index].first_event = event_to_be_linked
                event_links[link_index].score = best_score

            return None, event_links 
           
        position, existing_link = best_event.get_existing_link(event_to_be_linked.sportsbook)
        if existing_link and existing_link.score < best_score:
            existing_link.change_link(event_to_be_linked, position, best_score)
            return None, event_links 
        
        if not existing_link:
            return best_event.pk 
        
    return None, event_links 

# def link_odds(sport_id: int):
#     event_links = EventLink.objects.filter(sport_id=sport_id).select_related(
#         'first_event',
#         'second_event'
#     ).prefetch_related(
#         'first_event__odds',
#         'second_event__odds',
#         'first_event__odds__opportunity',
#         'second_event__odds__opportunity',
#         'first_event__odds__opportunity__parent',
#         'second_event__odds__opportunity__parent',
#         'first_event__odds__opportunity__parent__linked_opportunity',
#         'second_event__odds__opportunity__parent__linked_opportunity',
#         'first_event__odds__first_odd_links',
#         'first_event__odds__first_odd_links__second_odd',
#         'first_event__odds__first_odd_links__second_odd__event',
#         'first_event__odds__second_odd_links',
#         'first_event__odds__second_odd_links__first_odd',
#         'first_event__odds__second_odd_links__first_odd__event',
#         'second_event__odds__first_odd_links',
#         'second_event__odds__first_odd_links__second_odd',
#         'second_event__odds__first_odd_links__second_odd__event',
#         'second_event__odds__second_odd_links',
#         'second_event__odds__second_odd_links__first_odd',
#         'second_event__odds__second_odd_links__first_odd__event',
#     ).all()
#     odd_links = []
#     for event_link in event_links: 
#         first_odds = [odd for odd in event_link.first_event.odds.all() if not odd.is_linked_to_event(event_link.second_event)]
#         second_odds = [odd for odd in event_link.second_event.odds.all() if not odd.is_linked_to_event(event_link.first_event)]
#         linked = set()
#         for odd1 in first_odds:
#             for index2, odd2 in enumerate(second_odds):
#                 if index2 in linked: continue
#                 if odd1.can_be_linked(odd2):
#                     linked.add(index2)
#                     odd_links.append(OddLink(
#                         first_odd = odd1,
#                         second_odd = odd2,
#                         sport_id = sport_id,
#                     ))
#                     break
#     with transaction.atomic():
#         OddLink.objects.bulk_create(odd_links)
  
# def get_arbitrage_odds(sport_id: int):
#     potential_odd_pairs = OddLink.objects.filter(sport_id=sport_id).select_related(
#         'first_odd', 
#         'second_odd',
#         'first_odd__opportunity',
#         'second_odd__opportunity',
#         'first_odd__event',
#         'second_odd__event',
#         'first_odd__event__sportsbook',
#         'second_odd__event__sportsbook',
#     )
#     pairs_with_arbitrage = potential_odd_pairs.annotate(
#         first_odd_arbitrage=ExpressionWrapper(
#             Value(100.0) / F('first_odd__odd'),
#             output_field=FloatField()
#         ),
#         second_odd_arbitrage=ExpressionWrapper(
#             Value(100.0) / F('second_odd__odd'),
#             output_field=FloatField()
#         ),
#         total_arbitrage=Sum(F('first_odd_arbitrage') + F('second_odd_arbitrage'))
#     ).filter(total_arbitrage__lt=99.5).all()
    
#     update_arbitrage_bets(pairs_with_arbitrage, sport_id)

# def update_arbitrage_bets(odd_links: list[OddLink], sport_id: int):
#     if not odd_links:
#         with transaction.atomic():
#             ArbitrageBet.objects.filter(sport_id=sport_id).delete()
#         return

#     sport = Sport.objects.get(id=sport_id)
#     arbitrage_bets = ArbitrageBet.objects.prefetch_related(
#         'details'
#     ).filter(sport_id=sport_id).all()
#     arbitrage_bets_dict = {(arbitrage_bet.first_odd_id, arbitrage_bet.second_odd_id): arbitrage_bet for arbitrage_bet in arbitrage_bets}
#     bets_to_update = []
#     details_to_update = []
#     new_bets = []
#     new_details = []
#     for oddlink in odd_links:
#         if (oddlink.first_odd.pk, oddlink.second_odd.pk) in arbitrage_bets_dict:
#             arbitrage_bet = arbitrage_bets_dict[(oddlink.first_odd.pk, oddlink.second_odd.pk)]
#             arbitrage_bet.update_instance(oddlink)
#             bets_to_update.append(arbitrage_bet)
#             details = arbitrage_bet.details.all()
#             details[0].update_instance(oddlink.first_odd, oddlink)
#             details[1].update_instance(oddlink.second_odd, oddlink)
#             details_to_update.extend([details[0], details[1]])
#             continue

#         new_bet = ArbitrageBet(
#             first_odd_id=oddlink.first_odd.pk,
#             second_odd_id=oddlink.second_odd.pk,
#             sport_id=sport_id,
#             sport_name=sport.name,
#             profit=get_profit(odds_to_implied_pb([oddlink.first_odd.odd, oddlink.second_odd.odd]))
#         )
#         first_name = oddlink.first_odd.event.first_name
#         second_name = oddlink.second_odd.event.second_name
#         details = [
#             ArbitrageBetDetail(
#                 arbitrage_bet=new_bet,
#                 player_name=first_name,
#                 sportsbook_name=oddlink.first_odd.event.sportsbook.name,
#                 opportunity_name=oddlink.first_odd.opportunity.opp_description.replace('*1*', first_name).replace('*2*', second_name),
#                 odd=oddlink.first_odd.odd,
#                 amount=stake_for_arbitrage_bet(odds_to_implied_pb([oddlink.first_odd.odd]), odds_to_implied_pb([oddlink.first_odd.odd, oddlink.second_odd.odd]))
#             ),
#             ArbitrageBetDetail(
#                 arbitrage_bet=new_bet,
#                 player_name=second_name,
#                 sportsbook_name=oddlink.second_odd.event.sportsbook.name,
#                 opportunity_name=oddlink.second_odd.opportunity.opp_description.replace('*1*', first_name).replace('*2*', second_name),
#                 odd=oddlink.second_odd.odd,
#                 amount=stake_for_arbitrage_bet(odds_to_implied_pb([oddlink.second_odd.odd]), odds_to_implied_pb([oddlink.first_odd.odd, oddlink.second_odd.odd]))
#             )
#         ]
#         new_bets.append(new_bet)
#         new_details.extend(details)

#     used_pairs = [(oddlink.first_odd.pk, oddlink.second_odd.pk) for oddlink in odd_links]
#     with transaction.atomic(): 
#         ArbitrageBet.objects.bulk_update(bets_to_update, ['updated', 'profit'])
#         ArbitrageBetDetail.objects.bulk_update(details_to_update, ['odd', 'amount'])
#         ArbitrageBet.objects.bulk_create(new_bets)
#         ArbitrageBetDetail.objects.bulk_create(new_details)
#         arbitrage_bets_to_delete = [arbitrage_bet for key, arbitrage_bet in arbitrage_bets_dict.items() if key not in used_pairs]
#         for bet in arbitrage_bets_to_delete: 
#             bet.delete()

# def serialize_arbitrage_bet(arbitrage_bet: ArbitrageBet):
#     slovakia_timezone = pytz.timezone('Europe/Bratislava')
#     local_time = arbitrage_bet.updated.astimezone(slovakia_timezone)
#     return {
#         'id': arbitrage_bet.pk,
#         'updated': local_time.strftime('%Y-%m-%d %H:%M:%S'),
#         'first_odd_id': arbitrage_bet.first_odd_id,
#         'second_odd_id': arbitrage_bet.second_odd_id,
#         'sport_id': arbitrage_bet.sport_id,
#         'sport_name': arbitrage_bet.sport_name,
#         'profit': float(arbitrage_bet.profit),
#         'details': [
#             {
#                 'id': detail.pk,
#                 'player_name': detail.player_name,
#                 'sportsbook_name': detail.sportsbook_name,
#                 'opportunity_name': detail.opportunity_name,
#                 'odd': float(detail.odd),
#                 'amount': float(detail.amount)
#             }
#             for detail in arbitrage_bet.details.all()
#         ]
#     }

# def get_all_arbitrage_bets(): 
#     all_bets = ArbitrageBet.objects.prefetch_related(
#         'details'
#     ).all()
#     return [serialize_arbitrage_bet(arbitrage_bet) for arbitrage_bet in all_bets]

# async def send_data_to_clients(arbitrage_bets):
#     channel_layer = get_channel_layer()
#     group_name = 'scrape_updates'
#     await channel_layer.group_send(
#         group_name,
#         {
#             'type': 'group_message',
#             'data_type': DataType.MATCHDATA,
#             'data': arbitrage_bets,
#         }
#     ) 

async def broadcast_data(data_type, data):
    if isinstance(data, Enum):
        data = data.value

    channel_layer = get_channel_layer()
    group_name = 'scrape_updates'
    await channel_layer.group_send(
        group_name,
        {
            'type': 'group_message',
            'data_type': data_type,
            'data': data,
        }
    ) 