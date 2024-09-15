import asyncio
from enum import Enum
import logging
from .dataclass_models import EventModel, OddModel, MatchOpportunityResponse
from database.models import Sportsbook, Opportunity, Odd, Event, Sport
from django.db import transaction
from django.db.models import Q
from collections import defaultdict
from ..enums import DataType
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
    opportunities_dict_by_sport = get_relevant_opportunities(odds_to_create, sportsbook)

    for odd in odds_to_create:
        event = events_dict.get(odd.event_id, None)
        if event is None: continue
        opportunities_dict = opportunities_dict_by_sport[event.sport.pk]
        if odd.description in opportunities_dict: 
            opportunity = opportunities_dict[odd.description]
            new_odd = Odd(
                odd_id=odd.odd_id,
                code=odd.code,
                movement=odd.movement,
                odd=odd.odd,
                is_default=event.is_default,
                selected=odd.selected,
                locked=odd.locked,
                event=event,
                sportsbook=sportsbook,
                opportunity=opportunity
            )
            new_odds.append(new_odd)
            continue
        if (odd.description, event.sport.pk) in [(opp.description, opp.sport.pk) for opp in new_opportunities]: continue
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
    events = Event.objects.filter(sportsbook=sportsbook).prefetch_related('odds', 'odds__opportunity').all()
    if include_code:
        return {event.event_id: {(odd.odd_id, odd.code): odd for odd in event.odds.all()} for event in events}
    return {event.event_id: {odd.odd_id: odd for odd in event.odds.all()} for event in events}

def get_selected_events(sportsbook: Sportsbook) -> tuple[list[Event], set]:
    events = Event.objects.select_related('sport', 'parent').prefetch_related(
        'children',
        'odds',
        'odds__parent',
        'odds__opportunity',
        'odds__sportsbook',
        'odds__children',
        'odds__children__sportsbook',
    )

    if sportsbook.is_default:
        events = events.filter(sportsbook=sportsbook, selected=True).all()
    else: 
        events = events.filter(sportsbook=sportsbook, parent__selected=True).all()   

    result: list[Event] = []
    sport_ids = set()
    for event in events: 
        result.append(event)
        sport_ids.add(event.sport.pk)

    return result, sport_ids

def get_relevant_opportunities(odds: list[OddModel], sportsbook: Sportsbook) -> dict[tuple[int, str], Opportunity]:
    conditions = Q(sportsbook_id=sportsbook.pk)
    conditions &= Q(description__in=[odd.description for odd in odds])
    relevant_opportunities = Opportunity.objects.filter(conditions).order_by('sport_id').all()
    result_dict = { sport.pk: {} for sport in Sport.objects.all()}
    for opportunity in relevant_opportunities: 
        result_dict[opportunity.sport.pk][opportunity.description] = opportunity
    return result_dict

def send_updated_events(fetch_all: bool):
    sportsbook = Sportsbook.objects.get(is_default=True, selected=True)
    events, _ = get_selected_events(sportsbook)
    response = MatchOpportunityResponse.dataclass_from_models(events, fetch_all)
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

    parents_by_key = {}
    parents_by_sport = defaultdict(list[Event])
    for parent in parents: 
        parents_by_key[parent.pk] = parent
        parents_by_sport[parent.sport.pk].append(parent)

    events = Event.objects.select_related(
        'sportsbook',
        'sport',
        'parent',
    ).filter(is_default=False, parent__isnull=True).all()

    events_by_parent = defaultdict(list[Event])
    for event in events: 
        events_by_parent = find_best_parent(event, parents_by_sport[event.sport.pk], events_by_parent)
    
    events_to_update = []

    if -1 in events_by_parent:
        unassigned_events = events_by_parent.pop(-1)
        for event in unassigned_events: 
            event.parent = None
            events_to_update.append(event)

    for key, events in events_by_parent.items():
        parent = parents_by_key[key]
        for event in events: 
            event.add_parent(parent)
            events_to_update.append(event)

    with transaction.atomic():
        Event.objects.bulk_update(events_to_update, ['parent'])

def find_best_parent(event_to_be_linked: Event, parents: list[Event], events_by_parent: dict[int, list[Event]]) -> Event:
    sorted_parents = sorted(parents, key=lambda parent: parent.get_score(event_to_be_linked), reverse=True)

    best_parent = sorted_parents[0] if sorted_parents else None
    best_score = best_parent.get_score(event_to_be_linked) if best_parent else 0
        
    if best_parent and best_score >= 70:
        existing_child_index = next((index for index, event in enumerate(events_by_parent[best_parent.pk]) if event.sportsbook == event_to_be_linked.sportsbook), None)
        if existing_child_index is not None:
            if best_parent.get_score(event_to_be_linked) > best_parent.get_score(events_by_parent[best_parent.pk][existing_child_index]): 
                events_by_parent[best_parent.pk][existing_child_index] = event_to_be_linked

            return events_by_parent

        existing_child = best_parent.children.filter(sportsbook=event_to_be_linked.sportsbook).first()
        if existing_child is not None:
            if best_parent.get_score(event_to_be_linked) > best_parent.get_score(existing_child): 
                events_by_parent[-1].append(existing_child)
                events_by_parent[best_parent.pk].append(event_to_be_linked)

            return events_by_parent

        events_by_parent[best_parent.pk].append(event_to_be_linked)
    
    return events_by_parent

def link_odds():
    parents = Event.objects.filter(is_default=True).prefetch_related(
        'odds',
        'odds__opportunity',
        'children',
        'children__odds',
        'children__odds__parent',
        'children__odds__opportunity',
        'children__odds__opportunity__parent',
    ).all()

    odds_to_update = []
    for parent in parents: 
        parent_odds= parent.odds.all()
        children = parent.children.all()
        for child in children: 
            for odd in child.odds.filter(parent__isnull=True).all(): 
                for parent_odd in parent_odds: 
                    if odd.can_be_linked(parent_odd): 
                        odd.add_parent(parent_odd)
                        odds_to_update.append(odd)
                        break

    with transaction.atomic():
        Odd.objects.bulk_update(odds_to_update, ['parent'])

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