# utils/db/graph_builder.py
    """One time function to run load the data into the knowledge graph
    """
import os
import csv
from neo4j import GraphDatabase
from dotenv import load_dotenv
from loguru import logger
import re

load_dotenv()

class Neo4jGraphBuilder:
    def __init__(self):
        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("password", "password")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def run_query(self, query, parameters=None):
        with self.driver.session() as session:
            result = session.run(query, parameters)
            return [record for record in result]

    def build_graph(self):
        logger.info("Starting knowledge graph build...")
        self.run_query("MATCH (n) DETACH DELETE n") # Clear existing graph
        logger.info("Cleared old graph data.")

        self._create_constraints()
        self._ingest_tires_csv("utils/data/dealer_tyres.txt")
        self._ingest_tires_csv("utils/data/hiview_tyres.txt")
        self._ingest_tires_csv("utils/data/tires.csv")


        self._ingest_parts_csv("utils/data/data.csv")
        # Add more ingestion functions for your .txt files here
        
        logger.success("Knowledge graph build complete.")

    def _create_constraints(self):
        """Create uniqueness constraints for faster merges."""
        self.run_query("CREATE CONSTRAINT part_code IF NOT EXISTS FOR (p:Part) REQUIRE p.product_code IS UNIQUE")
        self.run_query("CREATE CONSTRAINT brand_name IF NOT EXISTS FOR (b:Brand) REQUIRE b.name IS UNIQUE")
        self.run_query("CREATE CONSTRAINT category_name IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE")
        logger.info("Created uniqueness constraints in Neo4j.")
    
    def _ingest_tires_csv(self, file_path):
        with open(file_path, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                try:
                    # Extract brand from item_name (e.g., "Apollo", "Falken")
                    brand_name = row['item_name'].split(' ')[0].strip().title()
                    
                    # A simple regex to find tire size like 175/70R13
                    size_match = re.search(r'(\d{2,3}(?:/\d{2,3})?R\d{2,3}C?)', row['item_name'])
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
                    self.run_query(query, {
                        'brand_name': brand_name,
                        'product_code': row['product_code'],
                        'item_name': row['item_name'],
                        'wholesale_price': row['wholesale_selling_price'],
                        'retail_price': row['retail_selling_price'],
                        'units': row['units'],
                        'tire_size': tire_size
                    })
                except Exception as e:
                    logger.warning(f"Skipping row in {file_path} due to error: {e} | Row: {row}")
        logger.info(f"Finished ingesting {file_path}.")

    def _ingest_parts_csv(self, file_path):
        # Similar logic for your general parts CSV
        logger.info(f"Finished ingesting {file_path}.")

if __name__ == "__main__":
    builder = Neo4jGraphBuilder()
    builder.build_graph()
    builder.close()