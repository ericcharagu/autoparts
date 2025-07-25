#!/usr/bin/env python3

# utils/db/graph_retriever.py
from typing import Any


import os
from neo4j import AsyncGraphDatabase
from dotenv import load_dotenv
from loguru import logger

load_dotenv()


class GraphRetriever:
    def __init__(self):
        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USER", "neo4j")
        password: str = os.getenv("NEO4J_PASSWORD", "NEO4J_PASSWORD")
        self._driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def close(self):
        await self._driver.close()

    async def search_parts_by_name(self, part_name: str) -> tuple[list[Any], Any]:
        """Find parts and their prices by name, using fuzzy search."""
        query = """
        MATCH (p:Part)-[:MANUFACTURED_BY]->(b:Brand)
        WHERE toLower(p.name) CONTAINS toLower($part_name)
        RETURN b.name AS brand, p.name AS part_name, p.product_code AS code, p.wholesale_price AS price
        LIMIT 5
        """
        async with self._driver.session() as session:
            result = await session.run(query, part_name=part_name)
            values = [record.values() for record in await result.fetch(5)] # #Get 5 the top 5 results and the stash the rest
            summary=await result.consume()
            return values, summary

    async def find_parts_for_vehicle(self, make: str, model: str) -> list:
        """Find parts suitable for a specific vehicle."""
        # This is a placeholder; you'd need to ingest vehicle compatibility data
        return []


# Singleton instance
graph_retriever = GraphRetriever()
