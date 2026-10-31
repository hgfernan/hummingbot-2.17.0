#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File: monitor_mid.py
Created: 2026-10-31 12:18:38
Purpose: Monitor mid price

@author: @hgfernan
"""

import csv  # class DictWriter,
import datetime  # class datetime, class timezone
import os  # path
from decimal import Decimal
from typing import Dict, List, Union

from pydantic import Field

from hummingbot import data_path
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import MarketDict
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase


class MonitorMidPriceConfig(StrategyV2ConfigBase):
    """
    Configuration parameters for monitoring mid price variation.
    """
    script_file_name: str = os.path.basename(__file__)

    connector_name: str = Field("binance_paper_trade", json_schema_extra={
        "prompt": lambda mi: "Exchange where this app will place orders",
        "prompt_on_new": True})

    trading_pair: str = Field("ETH-USDT", json_schema_extra={
        "prompt": lambda mi: "Trading pair where the bot will place orders",
        "prompt_on_new": True})

    n_ticks: int = Field(25, json_schema_extra={
        "prompt": lambda mi: "Number of time intervals to monitor",
        "prompt_on_new": True})

    def update_markets(self, markets: MarketDict) -> MarketDict:
        """
        Update markets information
        """

        markets[self.connector_name] = markets.get(self.connector_name, set()) | {self.trading_pair}

        # HINT Normal function termination
        return markets


class MonitorMidPrice(StrategyV2Base):
    """
    Management of the several purchases
    """

    def __init__(self,
                 connectors: Dict[str, ConnectorBase],
                 config: MonitorMidPriceConfig):

        super().__init__(connectors, config)

        self.config = config
        self.connector_name: str = self.config.connector_name
        self.trading_pair: str = self.config.trading_pair
        self.n_ticks = self.config.n_ticks

        self.connector = self.connectors[self.connector_name]

        self.tick_count: int = 0

        now: datetime.datetime = datetime.datetime.now(tz=datetime.timezone.utc)

        self.csv_name: str = "mid_price-" + \
                             self.trading_pair.replace("-", "_") + "-" + \
                             now.strftime("%Y%m%d_%H%M%S") + "-" + \
                             f"n{self.n_ticks:03d}.csv"

        self.csv_name = os.path.join(data_path(), self.csv_name)

        self.csv_header: List[str] = ["timestamp", "mid_price"]

        with open(self.csv_name, "w", encoding='utf-8') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=self.csv_header)

            writer.writeheader()

            self.logger().info("Created and nuked '%s'", self.csv_name)

        self.logger().info("Started")

    def on_tick(self) -> None:
        """
        Almost like a main program
        """

        if self.tick_count >= self.n_ticks:
            self.logger("Finished: recorded %d ticks of %d",
                        self.tick_count, self.n_ticks)

            # HINT finish application
            HummingbotApplication.main_application().stop()

            # HINT Return to avoid next steps
            return

        mid_price: Decimal = self.connector.get_mid_price(self.trading_pair)

        with open(self.csv_name, "a", encoding='utf-8') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=self.csv_header)

            now: datetime.datetime = \
                datetime.datetime.now(tz=datetime.timezone.utc)

            row: Dict[str, Union[int, str]] = {
                self.csv_header[0]: int(now.timestamp() * 1000),
                self.csv_header[1]: f"{mid_price:.2f}",
            }

            writer.writerow(row)

        self.tick_count += 1

        if (self.tick_count % 10) == 0:
            self.logger().info("Recorded %d", self.self.tick_count)
