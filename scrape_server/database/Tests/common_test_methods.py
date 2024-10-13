from django.db import connection, transaction
from database.models import Sportsbook, Sport, Event, Opportunity, Odd, SportsbookMarket

def reset_database():
    with transaction.atomic():
        Sportsbook.objects.all().delete()
        Sport.objects.all().delete()
        Event.objects.all().delete()
        Opportunity.objects.all().delete()
        Odd.objects.all().delete()
        SportsbookMarket.objects.all().delete()
    with connection.cursor() as cursor:
        cursor.execute("ALTER SEQUENCE database_sportsbook_id_seq RESTART WITH 1;")
        cursor.execute("ALTER SEQUENCE database_sport_id_seq RESTART WITH 1;")
        cursor.execute("ALTER SEQUENCE database_event_id_seq RESTART WITH 1;")
        cursor.execute("ALTER SEQUENCE database_opportunity_id_seq RESTART WITH 1;")
        cursor.execute("ALTER SEQUENCE database_odd_id_seq RESTART WITH 1;")
        cursor.execute("ALTER SEQUENCE database_sportsbookmarket_id_seq RESTART WITH 1;")