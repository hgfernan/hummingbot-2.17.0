#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: one_purchase.py
Created: 2026-10-23 00:37:51
Purpose: A single purchase

@author: @hgfernan
"""

import datetime  # class datetime, class timezone
import os  # path
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import MarketDict, OrderType
from hummingbot.core.event.events import BuyOrderCompletedEvent, OrderFilledEvent
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase


class TradeEvent(BaseModel):
    """
    All information about a trade event
    """

    ts: float = 0.0
    desc: str = ""
    order_id: str = ""
    base_amount: Decimal = Decimal(0.0)
    quote_amount: Decimal = Decimal(0.0)
    price: Optional[Decimal] = Decimal(0.0)

    def __init__(self,
                 ts: float,
                 desc: str,
                 order_id: str,
                 base_amount: Decimal,
                 quote_amount: Decimal,
                 price: Optional[Decimal] = None):
        super().__init__()

        self.ts = ts
        self.desc = desc
        self.order_id = order_id
        self.base_amount = base_amount
        self.quote_amount = quote_amount
        self.price = price


class OnePurchaseConfig(StrategyV2ConfigBase):
    """
    Configuration parameters for the one purchase.
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

    def update_markets(self, markets: MarketDict) -> MarketDict:
        """
        Update markets information
        """

        markets[self.connector_name] = markets.get(self.connector_name, set()) | {self.trading_pair}

        # HINT Normal function termination
        return markets


class OnePurchase(StrategyV2Base):
    """
    Management of one purchsae
    """

    def __init__(self, connectors: Dict[str, ConnectorBase], config: OnePurchaseConfig):
        super().__init__(connectors, config)
        self.config = config
        self.initialized = False
        self.connector_name = self.config.connector_name
        self.trading_pair = self.config.trading_pair
        self.amount_quote = self.config.amount_quote

        self.connector = self.connectors[self.connector_name]

        self.trade_events: List[TradeEvent] = []

        self.logger().info("Started")

    def place_buy_order(self, amount: Decimal):
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

        now: float = \
            datetime.datetime.now(tz=datetime.timezone.utc).timestamp()
        self.trade_events.append(
            TradeEvent(now, "Started", order_id, self.amount_quote, mid_price)
        )

    def on_tick(self):
        """
        Almost like a main program
        """

        if not self.initialized:
            self.logger().info("Will buy")

            self.place_buy_order(self.amount_quote)
            self.initialized = True

    def did_fill_order(self, event: OrderFilledEvent):
        """
        Monitor partial order fills
        """

        msg = f"{event.trade_type.name} {round(event.amount, 8)} " + \
            f"{event.trading_pair} at {round(event.price, 2)}"
        self.logger().info(msg)

        self.notify_hb_app_with_timestamp(msg)

        self.trade_events.append(
            TradeEvent(event.timestamp,
                       "Partial",
                       event.order_id,
                       base_amount=event.amount,
                       quote_amount=event.amount * event.price,
                       price=event.price,
                       )
        )

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
            TradeEvent(event.timestamp,
                       "Complete",
                       event.order_id,
                       base_amount=base_amount,
                       quote_amount=quote_amount,
                       price=None
                       )
        )

        # # HINT log events
        all_events: str = '\n'
        for trade_event in self.trade_events:
            line: str = f"{trade_event.ts:10.2f} "
            line += f"{trade_event.desc:<40} "
            line += f"{trade_event.order_id:<20} "
            line += f"{trade_event.base_amount:12.8f} "
            line += f"{trade_event.quote_amount:10.2f} "

            if trade_event.price is None:
                line += 10 * "-"
            else:
                line += f"{trade_event.price:10.2f}\n"

            all_events += line

        self.logger().info(all_events)

        # HINT finish application
        HummingbotApplication.main_application().stop()
