def stake_for_arbitrage_bet(BIP: float, CMM: float)-> float:
    return BIP/CMM

def get_profit(CMM: float) -> float:
    return (100/CMM - 1)

def odds_to_implied_pb(odds: list[float]) -> float:
    sum = 0
    for odd in odds:
        sum += 100/odd
    return sum