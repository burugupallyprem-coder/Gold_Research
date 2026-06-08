# strategy/h4_regime.py

class H4RegimeFilter:
    """
    Converts H4 into a regime state used by M15 system:
    - allows long bias
    - allows short bias
    - blocks trading (chop / anomaly)
    """

    def __init__(self):
        self.state = 0  # 1 = long bias, -1 = short bias, 0 = no-trade

    def update(self, h4_df):
        """
        Call ONLY when a new H4 candle closes
        """

        last = h4_df.iloc[-1]

        # Replace with YOUR real H4 logic (momentum / structure / yield filter)
        trend = last.get("trend", None)
        strength = last.get("strength", 0)

        if strength < 0.3:
            self.state = 0
        elif trend == "up":
            self.state = 1
        elif trend == "down":
            self.state = -1
        else:
            self.state = 0

        return self.state

    def allow_direction(self, direction: str) -> bool:
        """
        direction = "long" or "short"
        """

        if self.state == 0:
            return False

        if self.state == 1 and direction == "long":
            return True

        if self.state == -1 and direction == "short":
            return True

        return False