import asyncio
from enum import Enum
from django.db import transaction
from collections import defaultdict
from channels.layers import get_channel_layer
from traitlets import Any
from database.enums import DataType
from database.models import Sportsbook, Opportunity, Price, Event, SportsbookMarket
from database.Scrapes.dataclass_models import MatchOpportunityResponse, PriceModel

class EventHelper: 
    def __init__(self, sportsbook: Sportsbook) -> None:
        self.sportsbook = sportsbook

    def update_events(self, events_list: list[Event]) -> None:
        existing_events = Event.objects.filter(sportsbook=self.sportsbook).all()
        existing_events_dict = {event.event_id: event for event in existing_events}
        new_events = []
        events_to_update = []
        for event in events_list:
            if existing_event := existing_events_dict.get(event.event_id):
                existing_event.time = event.time
                events_to_update.append(existing_event)
                continue
            
            new_events.append(event)

        self.bulk_save_events(events_to_update, new_events, events_list)

    def bulk_save_events(self, events_to_update: list[Event], new_events: list[Event], events_list: list[Event]) -> None:
        with transaction.atomic():
            used_event_ids = {event.event_id for event in events_list}
            Event.objects.filter(sportsbook=self.sportsbook).exclude(event_id__in=used_event_ids).delete()

            Event.objects.bulk_update(events_to_update, ['time'])
            Event.objects.bulk_create(new_events)

    def get_selected_events(self) -> list[Event]:
        queryset = Event.objects.select_related('sport').prefetch_related(
            'prices',
            'children',
            'prices__children',
            'prices__opportunity',
            'prices__children__sportsbook',
        )

        if self.sportsbook.is_default:
            return queryset.filter(sportsbook=self.sportsbook, selected=True, used=False).all() 
        
        return queryset.filter(sportsbook=self.sportsbook, parent__selected=True, used=False).all() 
    
    
class PriceHelper: 
    def __init__(self, sportsbook: Sportsbook) -> None:
        self.sportsbook = sportsbook
        
    def get_allowed_markets(self) -> set[str]:
        markets = SportsbookMarket.objects.filter(sportsbook=self.sportsbook).values_list('value', flat=True)

        return set(markets)

    def update_prices(self, prices_to_create: list[PriceModel], prices_to_update: list[Price]) -> None:
        with transaction.atomic():
            Price.objects.bulk_update(prices_to_update, ['odds', 'locked', 'movement'])

        if not len(prices_to_create):
            return

        new_prices, new_opportunities = self.create_new_prices(prices_to_create)

        with transaction.atomic():
            Opportunity.objects.bulk_create(new_opportunities)
            Price.objects.bulk_create(new_prices)
    
    def create_new_prices(self, prices_to_create: list[PriceModel]) -> tuple[list[Price], list[Opportunity]]:
        new_prices = []
        new_opportunities = []
        opportunity_dict = self.get_opportunities([price_model.price.event for price_model in prices_to_create])
        new_opportunities_dict = {}

        for price_model in prices_to_create:
            sport_id = price_model.price.event.sport.pk
            sport_opportunities = opportunity_dict[sport_id]
            # case when opportunity already exists
            if price_model.description in sport_opportunities:
                price_model.price.opportunity = sport_opportunities[price_model.description]
                new_prices.append(price_model.price)
                continue

            key = (price_model.description, sport_id)
            # case when opportunity is already created but not saved to db
            if key in new_opportunities_dict:
                new_opportunity = new_opportunities_dict[key]
                price_model.price.opportunity = new_opportunity
                new_prices.append(price_model.price)
                continue

            # case when opportunity is not created yet
            new_opportunity = self.create_new_opportunity(price_model, sport_id)
            new_opportunities_dict[key] = new_opportunity
            new_opportunities.append(new_opportunity)
            price_model.price.opportunity = new_opportunity
            new_prices.append(price_model.price)

        return new_prices, new_opportunities
    
    def create_new_opportunity(self, price_model: PriceModel, sport_id: int) -> Opportunity:
        return Opportunity(
            description=price_model.description,
            is_default=self.sportsbook.is_default,
            sportsbook=self.sportsbook,
            sport_id=sport_id,
        )
    
    def get_opportunities(self, events: list[Event]) -> dict[int, dict[str, Opportunity]]:
        sport_ids = {event.sport.pk for event in events}
        relevant_opportunities = Opportunity.objects.filter(sportsbook=self.sportsbook, sport_id__in=sport_ids).all()
        result = { sport_id: {} for sport_id in sport_ids }
        for opportunity in relevant_opportunities:
            result[opportunity.sport.pk][opportunity.description] = opportunity
            
        return result


class ScrapeHelper:
    def __init__(self):
        self.event_helper = EventHelper(Sportsbook.objects.get(is_default=True, selected=True))

    def send_updated_events(self, fetch_all: bool) -> None:
        events = self.event_helper.get_selected_events()
        response = MatchOpportunityResponse.dataclass_from_models(events, fetch_all)
        asyncio.run(self.broadcast_data(DataType.MATCHDATA, response.dict))

    def unselect_events(self) -> None:
        events = Event.objects.filter(selected=True).all()
        for event in events:
            event.selected = False

        with transaction.atomic():
            Event.objects.bulk_update(events, ['selected'])

    def clear_unused_events(self) -> None:
        unused_sportsbooks = Sportsbook.objects.filter(selected=False).all()
        sb_ids = [sb.pk for sb in unused_sportsbooks]

        with transaction.atomic():
            Event.objects.filter(sportsbook_id__in=sb_ids).delete()

    def link_events(self) -> None:
        parents = self.fetch_parent_events()
        parents_by_key = {parent.pk: parent for parent in parents}
        parents_by_sport = self.group_parents_by_sport(parents)
        events = self.fetch_unlinked_events()
        events_by_parent = self.link_events_to_parents(events, parents_by_sport)
        self.assign_parents_to_events(events_by_parent, parents_by_key)
    
    def fetch_parent_events(self) -> list[Event]:
        return Event.objects.filter(is_default=True).select_related('sport').prefetch_related(
            'children',
            'children__sportsbook', 
        ).all()

    def group_parents_by_sport(self, parents: list[Event]) -> dict[int, list[Event]]:
        parents_by_sport = defaultdict(list)
        for parent in parents:
            parents_by_sport[parent.sport.pk].append(parent)
        return parents_by_sport
    
    def fetch_unlinked_events(self) -> list[Event]:
        return Event.objects.select_related('sportsbook').filter(is_default=False, parent__isnull=True).all()

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

    def find_best_parent(self, event_to_be_linked: Event, parents: list[Event], events_by_parent: dict[int, list[Event]]) -> None:
        sorted_parents = sorted(parents, key=lambda p: p.get_score(event_to_be_linked), reverse=True)
        best_parent = sorted_parents[0] if sorted_parents else None
        best_score = best_parent.get_score(event_to_be_linked) if best_parent else 0
            
        if best_parent and best_score >= 70:
            existing_child_index = next((i for i, e in enumerate(events_by_parent[best_parent.pk]) if e.sportsbook == event_to_be_linked.sportsbook), None)
            if existing_child_index is not None:
                # case when there are multiple events that are similar to parent. Highest score wins.
                if best_parent.get_score(event_to_be_linked) > best_parent.get_score(events_by_parent[best_parent.pk][existing_child_index]): 
                    events_by_parent[best_parent.pk][existing_child_index] = event_to_be_linked
                    
                return

            existing_child = best_parent.children.filter(sportsbook=event_to_be_linked.sportsbook).first()
            if existing_child is not None:
                # case when there is already linked child to parent event. We need to compare their scores and replace old event with new one if new score is higher.
                if best_parent.get_score(event_to_be_linked) > best_parent.get_score(existing_child): 
                    events_by_parent[-1].append(existing_child)
                    events_by_parent[best_parent.pk].append(event_to_be_linked)

                return

            events_by_parent[best_parent.pk].append(event_to_be_linked)

    def link_prices(self) -> None:
        parents = self.fetch_parents_with_prices()

        prices_to_update = []
        for parent in parents:
            for child in parent.children.all():
                prices_to_update.extend(self.link_child_prices_to_parent(child, parent.prices.all()))

        with transaction.atomic():
            Price.objects.bulk_update(prices_to_update, ['parent'])

    def fetch_parents_with_prices(self) -> list[Event]:
        return Event.objects.filter(is_default=True).prefetch_related(
            'children',
            'prices',
            'prices__opportunity',
            'children__prices',
            'children__prices__opportunity',
            'children__prices__opportunity__parent',
        ).all()
    
    def link_child_prices_to_parent(self, child: Event, parent_prices: list[Price]) -> list[Price]:
        prices_to_update = []
        for price in child.prices.filter(parent__isnull=True).all():
            for parent_price in parent_prices:
                if price.can_be_linked(parent_price):
                    price.add_parent(parent_price)
                    prices_to_update.append(price)
                    break
        return prices_to_update
    
    async def broadcast_data(self, data_type: DataType, data: Any) -> None:
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