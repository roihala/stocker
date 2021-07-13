import arrow


class Candles(object):
    def __init__(self, candles, start_time=None):
        self.candles = candles
        # For filtering out irrelevant candles
        if start_time:
            self.candles = self.__slice_by_time(start_time)

    def __slice_by_time(self, start_time):
        for index, candle in enumerate(self.candles):
            if arrow.get(candle['datetime']) >= arrow.get(start_time):
                return self.candles[index - 1:]

        raise ValueError(f"None of the candles match start_time: {start_time}")

    def get_percentage_by_period(self, minutes):
        # TODO: handle missing candles
        return 100 * (self.candles[minutes]['close'] / self.candles[0]['close'])
