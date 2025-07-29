import os
import csv
import re
import json
from neo4j import GraphDatabase
from dotenv import load_dotenv
from loguru import logger
from ollama import Client
from utils.llm.llm_base import (
    llm_model,
)  # Use the synchronous client for a one-off script

load_dotenv()

EXTRACTION_PROMPT = """
You are an expert data extraction agent. Your task is to analyze the following text chunk from an auto parts catalog and extract all products, their brand, category, specifications, and features into a structured JSON format.

RULES:
- The output must be a single JSON object containing a "products" key, which is a list of product objects.
- For 'category', use one of the following: 'Engine Oil', 'Transmission Fluid', 'Coolant', 'Grease', 'Fuel Additive', 'Cleaning Product', 'Repair Product', 'Car Care'.
- For 'specifications', create a list of key-value pairs. Common keys are 'Viscosity', 'Approval', 'Conformity', 'Volume', 'Type'.
- For 'features', create a list of short descriptive strings.
- If a value is not mentioned for a product, use an empty string "" or an empty list [].
- Output ONLY the JSON object and nothing else.

Here is the text chunk to analyze:
---
{text_chunk}
---

JSON Output:
"""


class Neo4jGraphBuilder:
    def __init__(self):
        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USER")
        password = os.getenv("NEO4J_PASSWORD")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.ollama_client = Client(host=os.getenv("OLLAMA_HOST"))
        self.llm_model = llm_model

    def close(self):
        self.driver.close()

    def run_query(self, query, parameters=None):
        with self.driver.session() as session:
            result = session.run(query, parameters)
            return [record for record in result]

    def build_graph(self):
        logger.info("Starting knowledge graph build...")
        self.run_query("MATCH (n) DETACH DELETE n")
        logger.info("Cleared old graph data.")

        self._create_constraints()
        self._ingest_csv("utils/data/tires.csv", "Tire")
        self._ingest_csv("utils/data/data.csv", "Part")
        self._ingest_text_file("utils/data/green_lubes.txt")
        # Add more .txt files here
        self._ingest_text_file("utils/data/dealer_tyres.txt")
        self._ingest_text_file("utils/data/hiview_care.txt")
        self._ingest_text_file("utils/data/hiview_tyres.txt")

        logger.success("Knowledge graph build complete.")

    def _create_constraints(self):
        self.run_query("DROP CONSTRAINT part_name IF EXISTS")
        self.run_query(
            "CREATE CONSTRAINT part_code IF NOT EXISTS FOR (p:Part) REQUIRE p.product_code IS UNIQUE"
        )
        self.run_query(
            "CREATE CONSTRAINT brand_name IF NOT EXISTS FOR (b:Brand) REQUIRE b.name IS UNIQUE"
        )
        self.run_query(
            "CREATE CONSTRAINT category_name IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE"
        )
        self.run_query(
            "CREATE CONSTRAINT feature_desc IF NOT EXISTS FOR (f:Feature) REQUIRE f.description IS UNIQUE"
        )
        self.run_query(
            "CREATE CONSTRAINT spec_val IF NOT EXISTS FOR (s:Specification) REQUIRE (s.type, s.value) IS UNIQUE"
        )
        logger.info("Created/updated uniqueness constraints in Neo4j.")

    def _ingest_csv(self, file_path, category):
        with open(file_path, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                try:
                    # Extract brand from item_name (e.g., "Apollo", "Falken")
                    brand_name = row["item_name"].split(" ")[0].strip().title()

                    # A simple regex to find tire size like 175/70R13
                    size_match = re.search(
                        r"(\d{2,3}(?:/\d{2,3})?R\d{2,3}C?)", row["item_name"]
                    )
                    tire_size = size_match.group(1) if size_match else "Unknown"

                    query = """
                    MERGE (b:Brand {name: $brand_name})
                    MERGE (c:Category {name: 'Tire'})
                    MERGE (p:Part {product_code: $product_code})
                    ON CREATE SET p.name = $item_name, p.wholesale_price = toFloat($wholesale_price), p.retail_price = toFloat($retail_price), p.stock = toInteger($units)
                    MERGE (p)-[:MANUFACTURED_BY]->(b)
                    MERGE (p)-[:BELONGS_TO]->(c)
                    MERGE (s:Specification {type: 'Tire Size', value: $tire_size})
                    MERGE (p)-[:HAS_SPEC]->(s)
                    """
                    self.run_query(
                        query,
                        {
                            "brand_name": brand_name,
                            "product_code": row["product_code"],
                            "item_name": row["item_name"],
                            "wholesale_price": row["wholesale_selling_price"],
                            "retail_price": row["retail_selling_price"],
                            "units": row["units"],
                            "tire_size": tire_size,
                        },
                    )
                except Exception as e:
                    logger.warning(
                        f"Skipping row in {file_path} due to error: {e} | Row: {row}"
                    )
        logger.info(f"Finished ingesting {file_path}.")

    def _ingest_text_file(self, file_path):
        logger.info(f"Starting ingestion for text file: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            full_text = f.read()

        # Split text into manageable chunks (e.g., by product or paragraph)
        chunks = full_text.split(
            "###"
        )  # Use a clear delimiter like '###' between product descriptions in your .txt files

        for chunk in chunks:
            if len(chunk.strip()) < 50:
                continue  # Skip very small chunks

            prompt = EXTRACTION_PROMPT.format(text_chunk=chunk)

            try:
                response = self.ollama_client.generate(
                    model=self.llm_model, prompt=prompt
                )
                json_text = response["response"]

                # Clean the LLM output to get only the JSON
                json_text = json_text[json_text.find("{") : json_text.rfind("}") + 1]
                data = json.loads(json_text)

                if "products" in data and isinstance(data["products"], list):
                    for product in data["products"]:
                        self._create_product_nodes(product, file_path)

            except json.JSONDecodeError:
                logger.error(
                    f"Failed to decode JSON from LLM output for chunk: {chunk[:100]}..."
                )
            except Exception as e:
                logger.error(f"An error occurred during LLM extraction: {e}")

        logger.info(f"Finished ingesting text file: {file_path}.")

    def _create_product_nodes(self, product_data: dict, source_file: str):
        query = """
        MERGE (b:Brand {name: $brand_name})
        MERGE (c:Category {name: $category})
        MERGE (p:Part {name: $product_name})
        ON CREATE SET p.description = $description, p.source_file = $source_file
        MERGE (p)-[:MANUFACTURED_BY]->(b)
        MERGE (p)-[:BELONGS_TO]->(c)

        WITH p
        UNWIND $specifications AS spec
        MERGE (s:Specification {type: spec.type, value: spec.value})
        MERGE (p)-[:HAS_SPEC]->(s)

        WITH p
        UNWIND $features AS feature_text
        MERGE (f:Feature {description: feature_text})
        MERGE (p)-[:HAS_FEATURE]->(f)
        """
        params = {
            "brand_name": product_data.get("brand", "Unknown"),
            "category": product_data.get("category", "Uncategorized"),
            "product_name": product_data.get("product_name"),
            "description": product_data.get("description", ""),
            "source_file": source_file,
            "specifications": product_data.get("specifications", []),
            "features": product_data.get("features", []),
        }
        if params["product_name"]:  # Only run if a product name was extracted
            self.run_query(query, params)
            logger.debug(f"Ingested product: {params['product_name']}")


if __name__ == "__main__":
    builder = Neo4jGraphBuilder()
    builder.build_graph()
    builder.close()
