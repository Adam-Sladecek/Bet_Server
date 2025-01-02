import asyncio
from enum import Enum
from django.db.models import Q
from django.db import transaction
from collections import defaultdict
from channels.layers import get_channel_layer
from database.enums import DataType
from database.models import Sportsbook, Opportunity, Odd, Event, Sport
from database.Scrapes.dataclass_models import EventModel, OddModel, MatchOpportunityResponse

class EventHelper: 
    def __init__(self, sportsbook: Sportsbook) -> None:
        self.sportsbook = sportsbook

    def update_events(self, events_list: list[EventModel], delete=True):
        existing_events = Event.objects.select_related('sportsbook').filter(sportsbook=self.sportsbook).all()
        existing_events_dict = {event.event_id: event for event in existing_events}
        new_events = []
        events_to_update = []
        for event_data in events_list:
            if event_data.event_id in existing_events_dict:
                existing_event = existing_events_dict[event_data.event_id]
                existing_event.time = event_data.time
                events_to_update.append(existing_event)
                continue
            
            new_event = self.create_new_event(event_data)
            new_events.append(new_event)

        self.bulk_save_events(events_to_update, new_events, delete, events_list)

    def create_new_event(self, event_data: EventModel) -> Event:
        return Event(
            event_id=event_data.event_id,
            league_id=event_data.league_id,
            time=event_data.time,
            home=event_data.home,
            away=event_data.away,
            is_default=self.sportsbook.is_default,
            selected=event_data.selected,
            sportsbook_id=event_data.sportsbook_id,
            sport_id=event_data.sport_id
        )
    
    def bulk_save_events(self, events_to_update: list[Event], new_events: list[Event], delete: bool, events_list: list[EventModel]) -> None:
        with transaction.atomic():
            if delete:
                used_event_ids = {event_data.event_id for event_data in events_list}
                Event.objects.filter(sportsbook=self.sportsbook).exclude(event_id__in=used_event_ids).delete()
            Event.objects.bulk_update(events_to_update, ['time'])
            Event.objects.bulk_create(new_events)

    def get_selected_events(self) -> tuple[list[Event], set]:
        events = self.fetch_selected_events()
        result = list(events)
        sport_ids = {event.sport.pk for event in events}

        return result, sport_ids

    def fetch_selected_events(self) -> list[Event]:
        queryset = Event.objects.select_related('sport', 'parent').prefetch_related(
            'children',
            'odds',
            'odds__parent',
            'odds__opportunity',
            'odds__sportsbook',
            'odds__children',
            'odds__children__sportsbook',
            'odds__children__event',
        )

        if self.sportsbook.is_default:
            return queryset.filter(sportsbook=self.sportsbook, selected=True, used=False).all() 
        return queryset.filter(sportsbook=self.sportsbook, parent__selected=True, used=False).all() 
    
    def update_selected_events(self, events_to_update: list[Event], events_to_delete: list[Event]):
        with transaction.atomic():
            for event in events_to_delete: 
                event.delete()
            Event.objects.bulk_update(events_to_update, ['time'])

    def delete_settled_events(self, event_ids: list[int]): 
        with transaction.atomic():
            Event.objects.filter(sportsbook=self.sportsbook).filter(event_id__in=event_ids).delete()

class OddHelper: 
    def __init__(self, sportsbook: Sportsbook) -> None:
        self.sportsbook = sportsbook

    def update_odds(self, odds_to_create: list[OddModel], odds_to_update: list[Odd]):
        events_dict = self.get_events_dict(odds_to_create)
        self.update_selected_odds(odds_to_update)

        new_odds, new_opportunities = self.process_odds(odds_to_create, events_dict)
            
        with transaction.atomic():
            Opportunity.objects.bulk_create(new_opportunities)
            Odd.objects.bulk_create(new_odds)

    def get_events_dict(self, odds_to_create: list[OddModel]) -> dict[int, Event]:
        event_ids = {odd.event_id for odd in odds_to_create}
        events = Event.objects.select_related('sport').filter(sportsbook=self.sportsbook, event_id__in=event_ids)
        return {event.event_id: event for event in events}
    
    def process_odds(self, odds_to_create: list[OddModel], events_dict: dict[int, Event]) -> tuple[list[Odd], list[Opportunity]]:
        new_odds = []
        new_opportunities = []
        opportunities_dict_by_sport = self.get_relevant_opportunities(odds_to_create)

        for odd in odds_to_create:
            event = events_dict.get(odd.event_id)
            if event is None:
                continue

            opportunities_dict = opportunities_dict_by_sport[event.sport.pk]
            if odd.description in opportunities_dict:
                new_odds.append(self.create_new_odd(odd, event, opportunities_dict[odd.description]))
            elif (odd.description, event.sport.pk) not in [(opp.description, opp.sport.pk) for opp in new_opportunities]:
                new_opportunities.append(self.create_new_opportunity(odd, event))

        return new_odds, new_opportunities
    
    def create_new_odd(self, odd: OddModel, event: Event, opportunity: Opportunity) -> Odd:
        return Odd(
            odd_id=odd.odd_id,
            code=odd.code,
            movement=odd.movement,
            odd=odd.odd,
            is_default=event.is_default,
            selected=odd.selected,
            locked=odd.locked,
            event=event,
            sportsbook=self.sportsbook,
            opportunity=opportunity
        )
    
    def create_new_opportunity(self, odd: OddModel, event: Event) -> Opportunity:
        return Opportunity(
            description=odd.description,
            is_default=event.is_default,
            sportsbook=self.sportsbook,
            sport=event.sport,
            market_id=odd.market_id
        )
    
    def get_relevant_opportunities(self, odds: list[OddModel]) -> dict[tuple[int, str], Opportunity]:
        descriptions = [odd.description for odd in odds]
        relevant_opportunities = Opportunity.objects.filter(
            sportsbook=self.sportsbook,
            description__in=descriptions
        ).order_by('sport_id').all()
        opportunities_by_sport = { sport.pk: {} for sport in Sport.objects.all()}
        for opportunity in relevant_opportunities: 
            opportunities_by_sport[opportunity.sport.pk][opportunity.description] = opportunity
        return opportunities_by_sport
    
    def update_selected_odds(self, odds_to_update: list[Odd]):
        with transaction.atomic():
            Odd.objects.bulk_update(odds_to_update, ['odd', 'locked', 'movement'])

    def update_movements(self, events: list[Event]):
        event_ids = [event.pk for event in events]
        odds = Odd.objects.filter(sportsbook=self.sportsbook, event_id__in=event_ids)
        for odd in odds: 
            odd.movement = 0

        with transaction.atomic():
            Odd.objects.bulk_update(odds, ['movement'])    

    def get_existing_odds(self, include_code: bool=False):
        events = Event.objects.filter(sportsbook=self.sportsbook).prefetch_related('odds', 'odds__opportunity').all()
        if include_code:
            return {event.event_id: {(odd.odd_id, odd.code): odd for odd in event.odds.all()} for event in events}
        return {event.event_id: {odd.odd_id: odd for odd in event.odds.all()} for event in events}

class ScrapeHelper:
    def __init__(self):
        self.event_helper = EventHelper(Sportsbook.objects.get(is_default=True, selected=True))

    def send_updated_events(self, fetch_all: bool):
        events, _ = self.event_helper.get_selected_events()
        response = MatchOpportunityResponse.dataclass_from_models(events, fetch_all)
        asyncio.run(self.broadcast_data(DataType.MATCHDATA, response.dict))

    def clear_unused_events(self):
        unused_sportsbooks = Sportsbook.objects.filter(selected=False).all()
        sb_ids = [sb.pk for sb in unused_sportsbooks]

        with transaction.atomic():
            Event.objects.filter(sportsbook_id__in=sb_ids).delete()

    def link_all_events(self):
        parents = self.fetch_parent_events()
        parents_by_key = {parent.pk: parent for parent in parents}
        parents_by_sport = self.group_parents_by_sport(parents)
        events = self.fetch_unlinked_events()
        events_by_parent = self.link_events_to_parents(events, parents_by_sport)
        self.assign_parents_to_events(events_by_parent, parents_by_key)

    def link_odds(self):
        parents = self.fetch_parents_with_odds()

        odds_to_update = []
        for parent in parents:
            for child in parent.children.all():
                odds_to_update.extend(self.link_child_odds_to_parent(child, parent.odds.all()))

        with transaction.atomic():
            Odd.objects.bulk_update(odds_to_update, ['parent'])

    def fetch_parent_events(self) -> list[Event]:
        return Event.objects.filter(is_default=True).select_related('sport').prefetch_related(
            'children',
            'children__sportsbook', 
            'children__sport'
        ).all()

    def group_parents_by_sport(self, parents: list[Event]) -> dict[int, list[Event]]:
        parents_by_sport = defaultdict(list)
        for parent in parents:
            parents_by_sport[parent.sport.pk].append(parent)
        return parents_by_sport
    
    def fetch_unlinked_events(self) -> list[Event]:
        return Event.objects.select_related('sportsbook', 'sport', 'parent').filter(is_default=False, parent__isnull=True).all()

    def link_events_to_parents(self, events: list[Event], parents_by_sport: dict[int, list[Event]]) -> dict[int, list[Event]]:
        events_by_parent = defaultdict(list)
        for event in events:
            self.find_best_parent(event, parents_by_sport[event.sport.pk], events_by_parent)
        return events_by_parent
    
    def assign_parents_to_events(self, events_by_parent: dict[int, list[Event]], parents_by_key: dict[int, Event]) -> None:
        events_to_update = []
        
        if -1 in events_by_parent:
            unassigned_events = events_by_parent.pop(-1)
            for event in unassigned_events:
                event.parent = None
                events_to_update.append(event)

        for parent_id, events in events_by_parent.items():
            parent = parents_by_key[parent_id]
            for event in events:
                event.add_parent(parent)
                events_to_update.append(event)

        with transaction.atomic():
            Event.objects.bulk_update(events_to_update, ['parent'])

    def find_best_parent(self, event_to_be_linked: Event, parents: list[Event], events_by_parent: dict[int, list[Event]]) -> Event:
        sorted_parents = sorted(parents, key=lambda p: p.get_score(event_to_be_linked), reverse=True)
        best_parent = sorted_parents[0] if sorted_parents else None
        best_score = best_parent.get_score(event_to_be_linked) if best_parent else 0
            
        if best_parent and best_score >= 70:
            existing_child_index = next((i for i, e in enumerate(events_by_parent[best_parent.pk]) if e.sportsbook == event_to_be_linked.sportsbook), None)
            if existing_child_index is not None:
                # case when there are multiple events that are similar to parent. Highest score wins.
                if best_parent.get_score(event_to_be_linked) > best_parent.get_score(events_by_parent[best_parent.pk][existing_child_index]): 
                    events_by_parent[best_parent.pk][existing_child_index] = event_to_be_linked
                return events_by_parent

            existing_child = best_parent.children.filter(sportsbook=event_to_be_linked.sportsbook).first()
            if existing_child is not None:
                # case when there is already linked child to parent event. We need to compare their scores and replace old event with new one if new score is higher.
                if best_parent.get_score(event_to_be_linked) > best_parent.get_score(existing_child): 
                    events_by_parent[-1].append(existing_child)
                    events_by_parent[best_parent.pk].append(event_to_be_linked)
                return events_by_parent

            events_by_parent[best_parent.pk].append(event_to_be_linked)
        
        return events_by_parent

    def fetch_parents_with_odds(self) -> list[Event]:
        return Event.objects.filter(is_default=True).prefetch_related(
            'odds',
            'odds__opportunity',
            'children',
            'children__odds',
            'children__odds__parent',
            'children__odds__opportunity',
            'children__odds__opportunity__parent',
        ).all()
    
    def link_child_odds_to_parent(self, child: Event, parent_odds: list[Odd]) -> list[Odd]:
        odds_to_update = []
        for odd in child.odds.filter(parent__isnull=True).all():
            for parent_odd in parent_odds:
                if odd.can_be_linked(parent_odd):
                    odd.add_parent(parent_odd)
                    odds_to_update.append(odd)
                    break
        return odds_to_update
    
    async def broadcast_data(self, data_type, data):
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