#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: buy_sell.py
Created: 2026-10-29 00:41:28
Purpose: Buy then sell with advantage

@author: @hgfernan
"""

import csv  # class DictWriter,
import datetime  # class datetime, class timezone
import os  # path
from decimal import Decimal
from enum import Enum, auto
from typing import Dict, List, Optional, Sequence

from pydantic import BaseModel, Field

from hummingbot import data_path
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import MarketDict, OrderType
from hummingbot.core.event.events import BuyOrderCompletedEvent, OrderFilledEvent
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase

# TODO for all events
# ... TODO if should_buy then buy
# ... TODO if should_sell then sell

# TODO did_complete_order
    # TODO if status == BUYING
        # TODO should_sell = True
    # TODO else if status = SELLING
        # TODO should_buy = True


class TradeStatus(Enum):
    INACTIVE = 0
    BUYING = auto()
    SELLING = auto()


class OverallInfo(BaseModel):
    """
    Overall information
    """

    clock_ts: float = 0.0
    status: TradeStatus = TradeStatus.INACTIVE
    price: Decimal = Decimal(0.0)
    base_balance: Decimal = Decimal(0.0)
    quote_balance: Decimal = Decimal(0.0)
    desc: str = ""

    def __init__(self,
                 clock_ts: float = 0.0,
                 status: TradeStatus = TradeStatus.INACTIVE,
                 price: Decimal = Decimal(0.0),
                 base_balance: Decimal = Decimal(0.0),
                 quote_balance: Decimal = Decimal(0.0),
                 desc: str = ""
                 ):

        super().__init__()

        self.clock_ts = clock_ts
        self.status = status
        self.price = price
        self.base_balance = base_balance
        self.base_balance = quote_balance
        self.desc = desc


class TradeEvent(BaseModel):
    """
    All information about a trade event
    """

    clock_ts: float = 0.0
    event_ts: float = 0.0
    side: str = ""
    desc: str = ""
    order_id: str = ""
    base_amount: Decimal = Decimal(0.0)
    quote_amount: Decimal = Decimal(0.0)
    price: Optional[Decimal] = None

    def __init__(self,
                 clock_ts: float,
                 event_ts: float,
                 side: str,
                 desc: str,
                 order_id: str,
                 base_amount: Decimal,
                 quote_amount: Decimal,
                 price: Optional[Decimal] = None):
        super().__init__()

        self.clock_ts = clock_ts
        self.event_ts = event_ts
        self.side = side
        self.desc = desc
        self.order_id = order_id
        self.base_amount = base_amount
        self.quote_amount = quote_amount
        self.price = price


class BuySellConfig(StrategyV2ConfigBase):
    """
    Configuration parameters for the buying and selling.
    """
    script_file_name: str = os.path.basename(__file__)

    connector_name: str = Field("binance_paper_trade", json_schema_extra={
        "prompt": lambda mi: "Exchange where this app will place orders",
        "prompt_on_new": True})

    trading_pair: str = Field("ETH-USDT", json_schema_extra={
        "prompt": lambda mi: "Trading pair where the bot will place orders",
        "prompt_on_new": True})

    amount_quote: Decimal = Field(25, json_schema_extra={
        "prompt": lambda mi: "Amount of the starting order to buy (in quote asset)",
        "prompt_on_new": True})

    n_cycles: Decimal = Field(10, json_schema_extra={
        "prompt": lambda mi: "Number of buy and sell cycles to execute",
        "prompt_on_new": True})

    def update_markets(self, markets: MarketDict) -> MarketDict:
        """
        Update markets information
        """

        markets[self.connector_name] = markets.get(self.connector_name, set()) | {self.trading_pair}

        # HINT Normal function termination
        return markets


class BuySell(StrategyV2Base):
    """
    Management of the buy-selll cycles
    """

    def __init__(self,
                 connectors: Dict[str, ConnectorBase],
                 config: BuySellConfig):

        super().__init__(connectors, config)
        self.config = config
        self.connector_name = self.config.connector_name
        self.trading_pair = self.config.trading_pair
        self.amount_quote = self.config.amount_quote
        self.n_cycles = self.config.n_cycles

        self.cycle_count: int = 0
        self.buy_price: float = 0.0

        fields: List[str] = self.trading_pair.split("-")
        self.base_name: str = fields[0]
        self.quote_name: str = fields[1]

        self.should_buy: bool = True
        self.should_sell: bool = False
        self.status: TradeStatus = TradeStatus.INACTIVE

        self.connector = self.connectors[self.connector_name]

        self.trade_events: List[TradeEvent] = []
        self.overall_infos: List[OverallInfo] = []

        self.logger().info("Started")

    def get_timestamp(self) -> float:
        """
        Get time from Epoch in seconds
        """

        return datetime.datetime.now(tz=datetime.timezone.utc).timestamp()

    def place_buy_order(self, amount: Decimal, desc: str) -> None:
        """
        Place a limit buy order
        """

        mid_price: Decimal = self.connector.get_mid_price(self.trading_pair)

        order_id: str = \
            self.buy(self.connector_name,
                     self.trading_pair,
                     amount / mid_price,
                     OrderType.LIMIT,
                     mid_price
                     )

        now: float = self.get_timestamp()
        self.trade_events.append(
            TradeEvent(now,
                       now,
                       "Buy",
                       desc,
                       order_id,
                       self.amount_quote,
                       mid_price
                       )
        )

        self.should_buy = False

    def place_sell_order(self, amount: Decimal, desc: str) -> None:
        """
        Place a limit buy order
        """

        order_id: str = \
            self.sell(self.connector_name,
                      self.trading_pair,
                      amount / self.buy_price,
                      OrderType.LIMIT,
                      self.buy_price
                     )

        now: float = self.get_timestamp()
        self.trade_events.append(
            TradeEvent(now,
                       now,
                       "Sell",
                       desc,
                       order_id,
                       self.amount_quote,
                       self.buy_price
                       )
        )

        self.should_sell = False

    def get_overall_info(self, desc: str) -> OverallInfo:
        """
        Compute balance and get mid price
        """

        result: OverallInfo = OverallInfo()

        result.clock_ts = self.get_timestamp()

        result.status = self.status
        result.price = self.buy_price

        result.base_balance = \
            self.connector.get_available_balance(self.base_name)
        result.quote_balance = \
            self.connector.get_available_balance(self.quote_name)

        result.desc = desc

        # HINT Normal function termination
        return result

    def save_csv(self, csv_name: str, data: Sequence[BaseModel]) -> bool:
        """
        Save a BaseModel list as a CSV file
        """

        msg: str = ""

        if len(data) <= 0:
            msg = "Empty data list. Can't create CSV file '{csv_name}'"
            self.logger().error(msg)

            # HINT Return to indicate failure
            return False

        field_names: List[str] = \
            list(data[0].model_dump().keys())

        with open(csv_name, "w", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=field_names)

            writer.writeheader()
            for row in data:
                writer.writerow(row.model_dump())

        # HINT Normal function termination
        return True

    def savel_all_csv(self) -> bool:
        """
        Save overall info and trade events as CSV files
        """

        result: bool = True
        suffix: str = ""
        csv_name: str = ""

        suffix += datetime.datetime.now(tz=datetime.timezone.utc)\
            .strftime("%Y%m%d_%H%M%S") + ".csv"

        csv_name = "overall_info-" + suffix
        csv_name = os.path.join(data_path(), csv_name)

        if not self.save_csv(csv_name=csv_name, data=self.overall_infos):
            result = False

        csv_name = "trade_events-" + suffix
        csv_name = os.path.join(data_path(), csv_name)

        if not self.save_csv(csv_name=csv_name, data=self.trade_events):
            result = False

        # HINT Normal function termination
        return result
