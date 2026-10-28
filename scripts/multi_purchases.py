#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: multi_purchases.py
Created: 2026-10-28 11:46:04
Purpose: A specifile number of purchases in HummingBot

@author: @hgfernn
"""


import csv  # class DictWriter,
import datetime  # class datetime, class timezone
import os  # path
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from hummingbot import data_path
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import MarketDict, OrderType
from hummingbot.core.event.events import BuyOrderCompletedEvent, OrderFilledEvent
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase


class OverallInfo(BaseModel):
    """
    Overall information
    """

    clock_ts: float = 0.0
    mid_price: Decimal = Decimal(0.0)
    base_balance: Decimal = Decimal(0.0)
    quote_balance: Decimal = Decimal(0.0)
    desc: str = ""

    def __init__(self,
                 clock_ts: float = 0.0,
                 mid_price: Decimal = Decimal(0.0),
                 base_balance: Decimal = Decimal(0.0),
                 quote_balance: Decimal = Decimal(0.0),
                 desc: str = ""
                 ):

        super().__init__()

        self.clock_ts = clock_ts
        self.mid_price = mid_price
        self.base_balance = base_balance
        self.base_balance = quote_balance
        self.desc = desc


class TradeEvent(BaseModel):
    """
    All information about a trade event
    """

    clock_ts: float = 0.0
    event_ts: float = 0.0
    desc: str = ""
    order_id: str = ""
    base_amount: Decimal = Decimal(0.0)
    quote_amount: Decimal = Decimal(0.0)
    mid_price: Optional[Decimal] = None

    def __init__(self,
                 clock_ts: float,
                 event_ts: float,
                 desc: str,
                 order_id: str,
                 base_amount: Decimal,
                 quote_amount: Decimal,
                 mid_price: Optional[Decimal] = None):
        super().__init__()

        self.clock_ts = clock_ts
        self.event_ts = event_ts
        self.desc = desc
        self.order_id = order_id
        self.base_amount = base_amount
        self.quote_amount = quote_amount
        self.mid_price = mid_price


class MultiPurchasesConfig(StrategyV2ConfigBase):
    """
    Configuration parameters for the several purchases.
    """
    script_file_name: str = os.path.basename(__file__)

    connector_name: str = Field("binance_paper_trade", json_schema_extra={
        "prompt": lambda mi: "Exchange where this app will place orders",
        "prompt_on_new": True})

    trading_pair: str = Field("ETH-USDT", json_schema_extra={
        "prompt": lambda mi: "Trading pair where the bot will place orders",
        "prompt_on_new": True})

    amount_quote: Decimal = Field(25, json_schema_extra={
        "prompt": lambda mi: "Amount of the order to buy (in quote asset)",
        "prompt_on_new": True})

    n_purchases: Decimal = Field(10, json_schema_extra={
        "prompt": lambda mi: "Number of purchases to execute",
        "prompt_on_new": True})

    def update_markets(self, markets: MarketDict) -> MarketDict:
        """
        Update markets information
        """

        markets[self.connector_name] = markets.get(self.connector_name, set()) | {self.trading_pair}

        # HINT Normal function termination
        return markets


class MultiPurchases(StrategyV2Base):
    """
    Management of the several purchases
    """

    def __init__(self,
                 connectors: Dict[str, ConnectorBase],
                 config: MultiPurchasesConfig):

        super().__init__(connectors, config)
        self.config = config
        self.connector_name = self.config.connector_name
        self.trading_pair = self.config.trading_pair
        self.amount_quote = self.config.amount_quote
        self.n_purchases = self.config.n_purchases

        self.purchase_count: int = 0
        fields: List[str] = self.trading_pair.split("-")
        self.base_name: str = fields[0]
        self.quote_name: str = fields[1]
        self.order_filled: bool = True

        self.connector = self.connectors[self.connector_name]

        self.trade_events: List[TradeEvent] = []
        self.overall_infos: List[OverallInfo] = []

        self.logger().info("Started")

    def get_timestamp(self) -> float:
        """
        Get time from Epoch in seconds
        """

        return datetime.datetime.now(tz=datetime.timezone.utc).timestamp()

    def place_buy_order(self, amount: Decimal) -> None:
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
                       "Started",
                       order_id,
                       self.amount_quote,
                       mid_price
                       )
        )

        self.order_filled = False

    def get_overall_info(self, desc: str) -> OverallInfo:
        """
        Compute balance and get mid price
        """

        result: OverallInfo = OverallInfo()

        result.clock_ts = self.get_timestamp()
        result.base_balance = \
            self.connector.get_available_balance(self.base_name)
        result.quote_balance = \
            self.connector.get_available_balance(self.quote_name)

        result.mid_price = \
            self.connector.get_mid_price(self.trading_pair)

        result.desc = desc

        # HINT Normal function termination
        return result

    def save_csv(self) -> bool:
        """
        Save overall info and trade events as CSV files
        """

        # result: bool = False
        suffix: str = "overall_info-"
        suffix += datetime.datetime.now(tz=datetime.timezone.utc)\
            .strftime("%Y%m%d_%H%M%S") + ".csv"
        csv_name: str = os.path.join(data_path(), suffix)

        if len(self.overall_infos) > 0:
            field_names: List[str] = \
                list(self.overall_infos[0].model_dump().keys())

            with open(csv_name, "w", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=field_names)

                writer.writeheader()
                for overall_info in self.overall_infos:
                    writer.writerow(overall_info.model_dump())

        else:
            return False

        # HINT Normal function termination
        return True

    def on_tick(self):
        """
        Almost like a main program
        """

        if self.purchase_count >= self.n_purchases:
            self.save_csv()

            # HINT finish application
            HummingbotApplication.main_application().stop()

        if self.order_filled:
            next_count: int = self.purchase_count + 1

            self.logger().info("Will start buy count #%02d", next_count)

            msg: str = f"Before buy #{next_count}"
            self.overall_infos.append(self.get_overall_info(msg))

            self.place_buy_order(self.amount_quote)
            msg = f"Buy #{next_count} placed"

            self.should_start = False

    def did_fill_order(self, event: OrderFilledEvent):
        """
        Monitor partial order fills
        """

        msg = f"{event.trade_type.name} {round(event.amount, 8)} " + \
            f"{event.trading_pair} at {round(event.price, 2)}"
        self.logger().info(msg)

        self.notify_hb_app_with_timestamp(msg)

        self.trade_events.append(
            TradeEvent(self.get_timestamp(),
                       event.timestamp,
                       "Partial",
                       event.order_id,
                       base_amount=event.amount,
                       quote_amount=event.amount * event.price,
                       mid_price=event.price,
                       )
        )

        self.overall_infos.append(self.get_overall_info("Partial fill"))

    def did_complete_buy_order(self, event: BuyOrderCompletedEvent):
        """
        Monitor the completion of the order, logs the trade history and leaves
        application
        """

        trading_pair: str = event.base_asset + "-" + event.quote_asset
        base_amount: Decimal = event.base_asset_amount
        quote_amount: Decimal = event.quote_asset_amount

        msg = f"{event.order_type.name} {trading_pair}: " + \
            f"base {base_amount} quote {quote_amount}"
        self.logger().info(msg)

        self.notify_hb_app_with_timestamp(msg)

        self.trade_events.append(
            TradeEvent(self.get_timestamp(),
                       event.timestamp,
                       "Order filled",
                       event.order_id,
                       base_amount=base_amount,
                       quote_amount=quote_amount,
                       mid_price=None
                       )
        )

        self.overall_infos.append(
            self.get_overall_info("Order filled")
        )

        self.purchase_count += 1
        self.order_filled = True
