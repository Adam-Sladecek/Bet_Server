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

    relevant_opportunities = Opportunity.objects.filter(conditions).all()

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
    events_to_be_linked = EventToBeLinked.objects.filter(tried_to_link=False, sport_id=sport_id).select_related(
        'event', 
        'sportsbook'
    ).all()
    deleted_links = set()
    for obj in events_to_be_linked:
        if obj.id in deleted_links: continue
        event = obj.event
        sportsbook = obj.sportsbook
        success, matching_object = link_event(event, sportsbook.id)
        if success:
            deleted_links.add(obj.id)
            obj.delete()
        else:
            obj.tried_to_link = True   
        if matching_object:
            deleted_links.add(matching_object.id)
            matching_object.delete()

def link_event(event: Event, sportsbook_id: int) -> tuple[bool, EventToBeLinked]:
    increment = timedelta(hours=1)
    potential_matches = (
        Event.objects.filter(
            sport_id=event.sport.id,
            sportsbook_id=sportsbook_id,
            date_time__lte=event.date_time + increment,
            date_time__gte=event.date_time - increment,
        ).all()
    )

    best_score = 0
    best_event = None

    for pmatch in potential_matches:
        score = (fuzz.token_sort_ratio(pmatch.first_name.strip().lower(), event.first_name.strip().lower()) +
                    fuzz.token_sort_ratio(pmatch.second_name.strip().lower(), event.second_name.strip().lower())) / 2.0
        if score > best_score:
            best_score = score
            best_event = pmatch

    if best_event and best_score >= 70:
        existing_match = EventLink.objects.filter(
            first_event__sport_id=event.sport.id
            ).filter(
            models.Q(first_event=best_event, second_event__sportsbook_id=event.sportsbook.id) |
            models.Q(second_event=best_event, first_event__sportsbook_id=event.sportsbook.id)
        ).first()

        if existing_match and existing_match.score < best_score:
            if existing_match.first_event == best_event: 
                event_to_be_linked = EventToBeLinked(
                    event=existing_match.second_event,
                    sportsbook_id=best_event.sportsbook.id,
                    sport_id=best_event.sport.id
                )
                event_to_be_linked.save()
                existing_match.second_event = event
                existing_match.score = best_score
                existing_match.save()
            else:
                event_to_be_linked = EventToBeLinked(
                    event=existing_match.first_event,
                    sportsbook_id=best_event.sportsbook.id,
                    sport_id=best_event.sport.id
                )
                event_to_be_linked.save()
                existing_match.first_event = event
                existing_match.score = best_score
                existing_match.save()
            return True, None    
        elif not existing_match:
            event_link = EventLink(
                first_event=event,
                second_event=best_event,
                score = best_score
            )
            event_link.save()

            matching_object = EventToBeLinked.objects.filter(
                event=best_event,
                sportsbook_id=event.sportsbook.id,
                sport_id=event.sport.id
            ).first()

            if matching_object:
                return True, matching_object
            return True, None

    return False, None 
        
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
def update_odds(odd_dictionary: dict[int, list[OddModel]], sport_id: int, sportsbook_id: int):
    logger = logging.getLogger('django')
    used_odd_ids = set()
    used_odd_ids.update([(odd.bet_id, odd.tip_type) for _, odds in odd_dictionary.items() for odd in odds])
    
    sportsbook = Sportsbook.objects.filter(id=sportsbook_id).first()
    events = Event.objects.filter(sportsbook=sportsbook, event_id__in=odd_dictionary.keys()).all()
    events_dict = {event.event_id: event for event in events}

    existing_odds = Odd.objects.filter(sportsbook=sportsbook, event__event_id__in=odd_dictionary.keys()).all()
    existing_odds_dict = {(odd.bet_id, odd.tip_type): odd for odd in existing_odds}

    assigned_odd_models = []
    unassigned_odd_models = []
    for _, odds in odd_dictionary.items():
        for odd in odds:
            if (odd.bet_id, odd.tip_type) in existing_odds_dict:
                assigned_odd_models.append(odd)
                continue
            unassigned_odd_models.append(odd)

    odds_to_update = []
    for odd in assigned_odd_models:
        existing_odd = existing_odds_dict[(odd.bet_id, odd.tip_type)]
        existing_odd.odd = odd.odd
        odds_to_update.append(existing_odd)
                
    Odd.objects.bulk_update(odds_to_update, ['odd'])

    new_odds = []
    new_odds_to_be_linked = []
    opportunities_dict = get_relevant_opportunities(unassigned_odd_models, sport_id, sportsbook_id)

    for odd in unassigned_odd_models:
        if (odd.bet_id, odd.tip_type) in opportunities_dict: 
            if not odd.odd or odd.event_id not in events_dict: continue
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
            new_odd_to_be_linked = OddToBeLinked(
                odd = new_odd,
                sport_id = sport_id
            )
            new_odds.append(new_odd)
            new_odds_to_be_linked.append(new_odd_to_be_linked)
            continue

        odd_dict = asdict(odd)
        json_string = json.dumps(odd_dict, indent=2)
        logger.warning(f'Opportunity for {json_string} was not found.')

    Odd.objects.bulk_create(new_odds)
    OddToBeLinked.objects.bulk_create(new_odds_to_be_linked)
    for existing_odd in existing_odds:
        if (existing_odd.bet_id, existing_odd.tip_type) not in used_odd_ids:
            existing_odd.delete()   

@transaction.atomic
def link_odds(sport_id: int):
    odds_to_be_linked = OddToBeLinked.objects.filter(tried_to_link=False, sport_id=sport_id).select_related(
        'odd', 
        'odd__opportunity',
        'odd__event'
    ).all()
    deleted_links = set()
    odd_links = []
    for obj in odds_to_be_linked:
        if obj.id in deleted_links: continue
        odd = obj.odd
        success, matching_object = link_odd(odd, odds_to_be_linked)
        if success and matching_object:
            odd_links.append(OddLink(
                first_odd = odd,
                second_odd = matching_object.odd
            ))
            deleted_links.add(obj.id)
            deleted_links.add(matching_object.id)
            matching_object.delete()
            obj.delete()
            continue
        obj.tried_to_link = True

    OddLink.objects.bulk_create(odd_links)

def link_odd(odd: Odd, odds_to_be_linked: list[OddToBeLinked]) -> tuple[bool, OddToBeLinked]:
    potential_opportunity_links = OpportunityLink.objects.filter(
        models.Q(first_opportunity=odd.opportunity) |
        models.Q(second_opportunity=odd.opportunity)
    ).select_related(
        'first_opportunity', 
        'second_opportunity'
    ).all()
    potential_opportunity_links_dict = {(opportunity_link.first_opportunity.id, opportunity_link.second_opportunity.id): True for opportunity_link in potential_opportunity_links}
    potential_event_links = EventLink.objects.filter(
        models.Q(first_event=odd.event) |
        models.Q(second_event=odd.event)
    ).select_related(
        'first_event', 
        'second_event'
    ).all()
    potential_event_links_dict = {(event_link.first_event.id, event_link.second_event.id): True for event_link in potential_event_links}
    for potential_odd in odds_to_be_linked:
        opportunity_link_exists = potential_opportunity_links_dict[(odd.opportunity.id, potential_odd.odd.opportunity.id)] or potential_opportunity_links_dict[(potential_odd.odd.opportunity.id, odd.opportunity.id)]
        event_link_exists = potential_event_links_dict[(odd.event.id, potential_odd.odd.event.id)] or potential_event_links_dict[(potential_odd.odd.event.id, odd.event.id)]
        if opportunity_link_exists and event_link_exists:
            return True, potential_odd
    return False, None    

@transaction.atomic
def get_arbitrage_odds(sport_id: int):
    potential_odd_pairs = OddLink.objects.filter(first_odd__event__sport_id=sport_id).select_related(
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
            Value(100.0) / F('first_odd__odd_odd'),
            output_field=FloatField()
        ),
        second_odd_arbitrage=ExpressionWrapper(
            Value(100.0) / F('second_odd__odd_odd'),
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
            arbitrage_bet.updated = datetime.now()
            details = arbitrage_bet.details
            details[0].odd = oddlink.first_odd.odd
            details[0].ammount = stake_for_arbitrage_bet(odds_to_implied_pb([oddlink.first_odd.odd]), odds_to_implied_pb([oddlink.first_odd.odd, oddlink.second_odd.odd]))
            details[1].odd = oddlink.second_odd.odd
            details[1].ammount = stake_for_arbitrage_bet(odds_to_implied_pb([oddlink.second_odd.odd]), odds_to_implied_pb([oddlink.first_odd.odd, oddlink.second_odd.odd]))
            continue

        new_bet = ArbitrageBet(
            updated=datetime.now(),
            first_odd_id=oddlink.first_odd.id,
            second_odd_id=oddlink.second_odd.id,
            sport=sport,
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