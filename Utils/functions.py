def stakeForArbitrageBet(BIP: float, CMM: float)-> float:
    return BIP/CMM

def getProfit(CMM: float) -> float:
    return (100/CMM - 1)

def oddsToImpliedPB(odds: list[float]) -> float:
    sum = 0
    for odd in odds:
        sum += 100/odd
    return sum