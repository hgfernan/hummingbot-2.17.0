#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: show_exchange.py
Created: 2026-10-29 18:34:20
Purpose: Study of exchange properties and methods

@author: @hgfernan
"""

#   import datetime  # class datetime, class timezone
import os  # path
import time  # sleep()
from decimal import Decimal

# from typing import Dict, List, Optional
from typing import Dict

# from pydantic import BaseModel, Field
from pydantic import Field

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.connector_base import ConnectorBase

# from hummingbot.core.data_type.common import MarketDict, OrderType
from hummingbot.core.data_type.common import MarketDict

# from hummingbot.core.event.events import BuyOrderCompletedEvent, OrderFilledEvent
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase


class ShowExchangeConfig(StrategyV2ConfigBase):
    """
    Configuration parameters for showing exchange information
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

    def update_markets(self, markets: MarketDict) -> MarketDict:
        """
        Update markets information
        """

        markets[self.connector_name] = markets.get(self.connector_name, set()) | {self.trading_pair}

        # HINT Normal function termination
        return markets


class OnePurchase(StrategyV2Base):
    """
    Main class
    """

    def __init__(self,
                 connectors: Dict[str, ConnectorBase],
                 config: ShowExchangeConfig):

        super().__init__(connectors, config)

        self.config = config
        self.connector_name = self.config.connector_name
        self.trading_pair = self.config.trading_pair
        self.amount_quote = self.config.amount_quote

        self.connector = self.connectors[self.connector_name]

    def on_tick(self):
        """
        Almost like a main program
        """

        self.logger().info("Started")

        self.logger().info(type(self.connector))
        self.logger().info(dir(self.connector))

        msg: str = f"{self.connector.estimate_fee_pct(is_maker=True)=}"
        self.logger().info(msg)

        msg: str = f"{self.connector.estimate_fee_pct(is_maker=False)=}"
        self.logger().info(msg)

        time.sleep(3)

        # HINT finish application
        HummingbotApplication.main_application().stop()
