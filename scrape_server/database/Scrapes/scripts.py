import logging
import json
from fuzzywuzzy import fuzz
from datetime import timedelta, datetime
from dataclasses import asdict
from Data import link
from .dataclass_models import EventModel, OddModel
from Utils import odds_to_implied_pb, get_profit, stake_for_arbitrage_bet
from database.models import Sportsbook, Sport, SportType, Opportunity, OpportunityLink, Odd, EventToBeLinked, Event, EventLink, ArbitrageBet, ArbitrageBetDetail, OddLink, OddToBeLinked
from django.db import transaction, models
from django.core.management import call_command
from django.db.models import Q, F, Value, FloatField, ExpressionWrapper, Sum
import pytz
from collections import defaultdict

def populate():
    with open("Data/data.json", encoding="utf-8") as file:
        contents = file.read()
        data = json.loads(contents)

        sports_books = [Sportsbook(**obj) for obj in data["sports_books"]]
        sport_types = [SportType(**obj) for obj in data["sport_types"]]
        sports = [Sport(**obj) for obj in data["sports"]]

        all_ops, all_links = link()

        opportunities = [Opportunity(**obj) for obj in all_ops]
        links = [OpportunityLink(**obj) for obj in all_links]
        with transaction.atomic():
            call_command('flush', '--noinput')
            for sports_book in sports_books:
                sports_book.save()
            for sport_type in sport_types:
                sport_type.save()
            for sport in sports:
                sport.save()
            for opportunity in opportunities:
                opportunity.save()
            for single_link in links:
                single_link.save()

def get_relevant_opportunities(odds: list[OddModel], sport_id: int, sportsbook_id: int) -> dict[tuple[int, str], Opportunity]:
    conditions = Q(
        sportsbook_id=sportsbook_id,
        sport_id=sport_id,
    )
    conditions &= Q(tip_type__in=[odd.tip_type for odd in odds])
    conditions &= Q(opp_number__in=[odd.opp_number for odd in odds])
    conditions &= Q(market_id__in=[odd.market_id for odd in odds])
    conditions &= Q(bet_order__in=[odd.bet_order for odd in odds])

    if sportsbook_id != 5:
        conditions &= Q(opp_description__in=[odd.opp_description for odd in odds])

    relevant_opportunities = Opportunity.objects.filter(conditions).prefetch_related(
        'first_opportunity_links', 
        'second_opportunity_links'
    ).all()

    opportunities_dict = {
        (opportunity.tip_type, opportunity.opp_number, opportunity.market_id, opportunity.bet_order, opportunity.opp_description): opportunity
        for opportunity in relevant_opportunities
    }

    result = {}
    for odd in odds:
        key = (odd.bet_id, odd.tip_type)
        oppkey = (odd.tip_type, odd.opp_number, odd.market_id, odd.bet_order, odd.opp_description)
        opportunity = opportunities_dict.get(oppkey)
        if opportunity:
            result[key] = opportunity

    return result

@transaction.atomic
def link_all_events(sport_id: int):
    events_to_be_linked = EventToBeLinked.objects.filter(sport_id=sport_id).select_related(
        'event',
        'sportsbook'
    ).order_by('sportsbook_id').all()

    events_tbl_by_sportsbook = defaultdict(list[EventToBeLinked])
    for event_to_be_linked in events_to_be_linked:
        sportsbook_id = event_to_be_linked.sportsbook.id
        events_tbl_by_sportsbook[sportsbook_id].append(event_to_be_linked)

    events = Event.objects.filter(sport_id=sport_id).select_related(
        'sportsbook'
    ).order_by('sportsbook_id').all()

    events_by_sportsbook = defaultdict(list[Event])
    for event in events:
        sportsbook_id = event.sportsbook.id
        events_by_sportsbook[sportsbook_id].append(event)

    deleted_links = set()
    for sb_id, events_tbl in events_tbl_by_sportsbook.items():
        filtered_events_tbl = [ev for ev in events_tbl if ev.id not in deleted_links]
        deleted_links = link_events(filtered_events_tbl, events_by_sportsbook[sb_id], deleted_links, sport_id)

    EventToBeLinked.objects.filter(id__in=deleted_links).delete()                  

def link_events(events_to_be_linked: list[EventToBeLinked], events: list[Event], deleted_links: set, sport_id: int) -> set: 
    for etbl in events_to_be_linked: 
        matching_etbl = link_event(etbl, events, sport_id)
        deleted_links.add(etbl.id)
        if matching_etbl:
            deleted_links.add(matching_etbl.id)
    return deleted_links

def link_event(event_to_be_linked: EventToBeLinked, events: list[Event], sport_id: int) -> EventToBeLinked:
    increment = timedelta(hours=1)
    potential_matches: list[Event] = [event for event in events if event.date_time <=event_to_be_linked.event.date_time + increment and event.date_time >=event_to_be_linked.event.date_time - increment]

    best_score = 0
    best_event = None

    for pmatch in potential_matches:
        score = (fuzz.token_sort_ratio(pmatch.first_name.strip().lower(), event_to_be_linked.event.first_name.strip().lower()) +
                    fuzz.token_sort_ratio(pmatch.second_name.strip().lower(), event_to_be_linked.event.second_name.strip().lower())) / 2.0
        if score > best_score:
            best_score = score
            best_event = pmatch

    if best_event and best_score >= 70:
        existing_match = EventLink.objects.filter(
            sport_id=sport_id
            ).filter(
            models.Q(first_event=best_event, second_event__sportsbook_id=event_to_be_linked.event.sportsbook.id) |
            models.Q(second_event=best_event, first_event__sportsbook_id=event_to_be_linked.event.sportsbook.id)
        ).first()

        if existing_match and existing_match.score < best_score:
            if existing_match.first_event == best_event: 
                event_to_be_linked = EventToBeLinked(
                    sport_id=sport_id,
                    sportsbook_id=best_event.sportsbook.id,
                    event=existing_match.second_event
                )
                event_to_be_linked.save()
                existing_match.second_event = event_to_be_linked.event
                existing_match.score = best_score
                existing_match.save()
            else:
                event_to_be_linked = EventToBeLinked(
                    sport_id=sport_id,
                    sportsbook_id=best_event.sportsbook.id,
                    event=existing_match.first_event
                )
                event_to_be_linked.save()
                existing_match.first_event = event_to_be_linked.event
                existing_match.score = best_score
                existing_match.save()
            return None    
        elif not existing_match:
            event_link = EventLink(
                sport_id=sport_id,
                first_event=best_event,
                second_event=event_to_be_linked.event,
                score=best_score
            )
            event_link.save()

            matching_object = EventToBeLinked.objects.filter(
                sport_id=sport_id,
                sportsbook=event_to_be_linked.event.sportsbook,
                event=best_event
            ).first()

            if matching_object:
                return matching_object
            return None

    return None 
        
@transaction.atomic
def update_events(events_list: list[EventModel], sport_id: int, sportsbook_id: int):
    sports_books = Sportsbook.objects.filter(selected=True).all()
    existing_events = Event.objects.filter(sport_id=sport_id, sportsbook_id=sportsbook_id).all()
    existing_events_dict = {event.event_id: event for event in existing_events}
    events_to_update = []
    new_events = []
    new_event_links = []
    for event_data in events_list:
        if event_data.event_id in existing_events_dict:
            existing_event = existing_events_dict[event_data.event_id]
            if existing_event.date_time != event_data.date_time:
                existing_event.date_time = event_data.date_time
                events_to_update.append(existing_event)
            continue
        
        new_event = Event(
            sport_id=event_data.sport_id,
            sportsbook_id=event_data.sportsbook_id,
            event_id=event_data.event_id,
            date_time=event_data.date_time,
            first_name=event_data.first_name,
            second_name=event_data.second_name,
        )
        new_events.append(new_event)
        for sportsbook in sports_books:
            if sportsbook.id == sportsbook_id:
                continue

            new_event_links.append(EventToBeLinked( 
                event=new_event,
                sportsbook=sportsbook,
                sport_id=sport_id
            ))
    Event.objects.bulk_update(events_to_update, ['date_time'])
    Event.objects.bulk_create(new_events)
    EventToBeLinked.objects.bulk_create(new_event_links)
    used_event_ids = [event_data.event_id for event_data in events_list]
    Event.objects.filter(sport_id=sport_id, sportsbook_id=sportsbook_id).exclude(event_id__in=used_event_ids).delete()

@transaction.atomic
def get_existing_odds(sportsbook_id: int, sport_id: int, include_type: bool=False):
    sportsbook = Sportsbook.objects.filter(id=sportsbook_id).first()
    sport = Sport.objects.filter(id=sport_id).first()
    events = Event.objects.filter(sportsbook=sportsbook, sport=sport).prefetch_related('odds').all()
    if include_type:
        return {event.event_id: {(odd.bet_id, odd.tip_type): odd for odd in event.odds.all()} for event in events}
    return {event.event_id: {odd.bet_id: odd for odd in event.odds.all()} for event in events}

@transaction.atomic
def update_odds(odds_to_create: list[OddModel], odds_to_update: list[Odd], odds_to_delete: list[Odd], sport_id: int, sportsbook_id: int):
    logger = logging.getLogger('django')
    
    sportsbook = Sportsbook.objects.filter(id=sportsbook_id).first()
    events = Event.objects.filter(sportsbook=sportsbook, event_id__in=[odd.event_id for odd in odds_to_create]).all()
    events_dict = {event.event_id: event for event in events}

    Odd.objects.bulk_update(odds_to_update, ['odd'])
    ids_to_delete = [odd.pk for odd in odds_to_delete]
    Odd.objects.filter(pk__in=ids_to_delete).delete()

    new_odds = []
    new_odds_to_be_linked = []
    opportunities_dict = get_relevant_opportunities(odds_to_create, sport_id, sportsbook_id)

    for odd in odds_to_create:
        if (odd.bet_id, odd.tip_type) in opportunities_dict: 
            event = events_dict[odd.event_id]
            opportunity = opportunities_dict[(odd.bet_id, odd.tip_type)]
            new_odd = Odd(
                bet_id=odd.bet_id,
                tip_type=odd.tip_type,
                sportsbook=sportsbook,
                event=event,
                odd=odd.odd,
                opportunity=opportunity
            )
            for link in opportunity.first_opportunity_links.all():
                new_odd_to_be_linked = OddToBeLinked(
                    odd = new_odd,
                    sport_id = sport_id, 
                    opportunity_link = link,
                    event=event
                )
                new_odds_to_be_linked.append(new_odd_to_be_linked)
            for link in opportunity.second_opportunity_links.all():
                new_odd_to_be_linked = OddToBeLinked(
                    odd = new_odd,
                    sport_id = sport_id, 
                    opportunity_link = link,
                    event=event
                )
                new_odds_to_be_linked.append(new_odd_to_be_linked)    
            new_odds.append(new_odd)
            continue

        odd_dict = asdict(odd)
        json_string = json.dumps(odd_dict, indent=2)
        logger.warning(f'Opportunity for {json_string} was not found.')

    Odd.objects.bulk_create(new_odds)
    OddToBeLinked.objects.bulk_create(new_odds_to_be_linked)

@transaction.atomic
def link_odds(sport_id: int):
    event_links = EventLink.objects.filter(sport_id=sport_id).select_related(
        'first_event', 
        'second_event'
    ).prefetch_related(
        'first_event__oddstobelinked', 
        'second_event__oddstobelinked',
        'first_event__oddstobelinked__opportunity_link',
        'second_event__oddstobelinked__opportunity_link'
    ).all()
    deleted_links = set()
    odd_links = []
    for event_link in event_links: 
        first_oddstobelinked = event_link.first_event.oddstobelinked.all()
        second_oddstobelinked = event_link.second_event.oddstobelinked.all()
        for odd_to_be_linked_1 in first_oddstobelinked:
            for odd_to_be_linked_2 in second_oddstobelinked:
                if odd_to_be_linked_2.id in deleted_links: continue
                if odd_to_be_linked_1.opportunity_link == odd_to_be_linked_2.opportunity_link:
                    odd_links.append(OddLink(
                        first_odd = odd_to_be_linked_1.odd,
                        second_odd = odd_to_be_linked_2.odd,
                        sport_id = sport_id,
                        opportunity_link = odd_to_be_linked_1.opportunity_link
                    ))
                    deleted_links.add(odd_to_be_linked_1.id)
                    deleted_links.add(odd_to_be_linked_2.id)
                    break
    OddToBeLinked.objects.filter(id__in=deleted_links).delete()                
    OddLink.objects.bulk_create(odd_links)
  
@transaction.atomic
def get_arbitrage_odds(sport_id: int):
    potential_odd_pairs = OddLink.objects.filter(sport_id=sport_id).select_related(
        'first_odd', 
        'second_odd',
        'first_odd__opportunity',
        'second_odd__opportunity',
        'first_odd__event',
        'second_odd__event',
        'first_odd__event__sportsbook',
        'second_odd__event__sportsbook',
    )
    pairs_with_arbitrage = potential_odd_pairs.annotate(
        first_odd_arbitrage=ExpressionWrapper(
            Value(100.0) / F('first_odd__odd'),
            output_field=FloatField()
        ),
        second_odd_arbitrage=ExpressionWrapper(
            Value(100.0) / F('second_odd__odd'),
            output_field=FloatField()
        ),
        total_arbitrage=Sum(F('first_odd_arbitrage') + F('second_odd_arbitrage'))
    ).filter(total_arbitrage__lt=100).all()
    
    update_arbitrage_bets(pairs_with_arbitrage, sport_id)

def update_arbitrage_bets(odd_links: list[OddLink], sport_id: int):
    if not odd_links:
        ArbitrageBet.objects.filter(sport_id=sport_id).delete()
        return

    sport = Sport.objects.get(id=sport_id)
    arbitrage_bets = ArbitrageBet.objects.filter(sport_id=sport_id)
    arbitrage_bets_dict = {(arbitrage_bet.first_odd_id, arbitrage_bet.second_odd_id): arbitrage_bet for arbitrage_bet in arbitrage_bets}
    
    for oddlink in odd_links:
        if (oddlink.first_odd.id, oddlink.second_odd.id) in arbitrage_bets_dict:
            arbitrage_bet = arbitrage_bets_dict[(oddlink.first_odd.id, oddlink.second_odd.id)]
            arbitrage_bet.updated = datetime.now(pytz.utc)
            arbitrage_bet.profit = get_profit(odds_to_implied_pb([oddlink.first_odd.odd, oddlink.second_odd.odd]))
            arbitrage_bet.save()
            details = arbitrage_bet.details.all()
            details[0].odd = oddlink.first_odd.odd
            details[0].ammount = stake_for_arbitrage_bet(odds_to_implied_pb([oddlink.first_odd.odd]), odds_to_implied_pb([oddlink.first_odd.odd, oddlink.second_odd.odd]))
            details[1].odd = oddlink.second_odd.odd
            details[1].ammount = stake_for_arbitrage_bet(odds_to_implied_pb([oddlink.second_odd.odd]), odds_to_implied_pb([oddlink.first_odd.odd, oddlink.second_odd.odd]))
            details[0].save()
            details[1].save()
            continue

        new_bet = ArbitrageBet(
            updated=datetime.now(pytz.utc),
            first_odd_id=oddlink.first_odd.id,
            second_odd_id=oddlink.second_odd.id,
            sport_id=sport_id,
            sport_name=sport.name,
            profit=get_profit(odds_to_implied_pb([oddlink.first_odd.odd, oddlink.second_odd.odd]))
        )
        first_name = oddlink.first_odd.event.first_name
        second_name = oddlink.second_odd.event.second_name
        details = [
            ArbitrageBetDetail(
                arbitrage_bet=new_bet,
                player_name=first_name,
                sportsbook_name=oddlink.first_odd.event.sportsbook.name,
                opportunity_name=oddlink.first_odd.opportunity.opp_description.replace('*1*', first_name).replace('*2*', second_name),
                odd=oddlink.first_odd.odd,
                ammount=stake_for_arbitrage_bet(odds_to_implied_pb([oddlink.first_odd.odd]), odds_to_implied_pb([oddlink.first_odd.odd, oddlink.second_odd.odd]))
            ),
            ArbitrageBetDetail(
                arbitrage_bet=new_bet,
                player_name=second_name,
                sportsbook_name=oddlink.second_odd.event.sportsbook.name,
                opportunity_name=oddlink.second_odd.opportunity.opp_description.replace('*1*', first_name).replace('*2*', second_name),
                odd=oddlink.second_odd.odd,
                ammount=stake_for_arbitrage_bet(odds_to_implied_pb([oddlink.second_odd.odd]), odds_to_implied_pb([oddlink.first_odd.odd, oddlink.second_odd.odd]))
            )
        ]
        new_bet.save()
        ArbitrageBetDetail.objects.bulk_create(details)

    used_pairs = [(oddlink.first_odd.id, oddlink.second_odd.id) for oddlink in odd_links]
    arbitrage_bets_to_delete = [arbitrage_bet for key, arbitrage_bet in arbitrage_bets_dict.items() if key not in used_pairs]
    for bet in arbitrage_bets_to_delete: 
        bet.delete()
        