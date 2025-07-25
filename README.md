Of course. A good README.md is essential for any project. It serves as the front door, guiding users and developers on how to get started, understand the architecture, and contribute effectively.

Here is a comprehensive README.md file tailored to your project. It includes an overview, a clear setup guide, an explanation of the architecture, and instructions on how to use and extend the system.

File: README.md
Generated markdown
# Lane AI: WhatsApp-Powered Auto Parts Assistant

This project is an AI-powered customer care assistant for "Lane," a wholesale auto parts supplier based in Kenya. The assistant is accessible via WhatsApp and a web interface, designed to help mechanics and B2B clients find parts, get pricing, see their savings, and process orders efficiently.

The system leverages a hybrid approach of a **Knowledge Graph (Neo4j)** for structured data retrieval and a **Vector Database (Qdrant)** for semantic search on unstructured text, providing a rich context to a local Large Language Model (LLM) powered by Ollama.

## ✨ Features

-   **Multi-Channel Support:** Interact via a simple web UI or directly through WhatsApp.
-   **Intelligent Context Generation:**
    -   **Vector Search (RAG):** Uses Qdrant and `nomic-embed-text` to find relevant information from product catalogs and documents.
    -   **Knowledge Graph:** Uses Neo4j to answer precise, structured queries about parts, brands, and prices.
    -   **Conversation History:** Maintains user-specific conversation history using a Valkey (Redis) cache.
-   **Image Processing:** Users can send images of parts, which are analyzed by a multi-modal LLM (`qwen2.5vl:3b`) to identify products.
-   **Robust & Scalable Backend:** Built with FastAPI, ensuring high performance and asynchronous request handling.
-   **Containerized Deployment:** Fully containerized with Docker and Docker Compose for easy setup and consistent environments.
-   **Culturally-Tuned Persona:** The chatbot's personality is specifically designed for the Kenyan market, using a mix of English, Swahili, and Sheng.

## 🏗️ System Architecture

The application consists of several interconnected services managed by Docker Compose:

-   **`llm_service` (FastAPI App):** The main application that handles API requests, webhook logic, and orchestrates the AI pipeline.
-   **`ollama`:** Runs the primary text-based LLM (e.g., `qwen:0.5b`) for generating conversational responses.
-   **`ollama_embedding`:** Runs the text embedding model (`nomic-embed-text`) used by the vector database.
-   **`qdrant`:** The vector database for performing semantic search (Retrieval-Augmented Generation).
-   **`neo4j`:** The graph database for storing and querying structured product data.
-   **`postgres`:** A PostgreSQL database for storing user, customer, and order information.
-   **`valkey`:** An in-memory data store (Redis fork) for caching conversation history and ensuring webhook idempotency.

 <!-- It's highly recommended to create a simple diagram -->

---

## 🚀 Getting Started

Follow these steps to set up and run the project locally.

### Prerequisites

-   [Docker](https://www.docker.com/get-started) and Docker Compose
-   A `.env` file configured with your credentials.
-   Secrets files for sensitive information.

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd ericcharagu-autoparts

2. Configure Environment Variables

Create a .env file in the root directory by copying the example. This file holds non-sensitive configuration.


Now, edit the .env file with your specific settings:

Generated env
# .env

# PostgreSQL Database Connection
DB_HOST=db_server
DB_PORT=5432
DB_NAME=autoparts_db
DB_USER=postgres

# Valkey/Redis Connection
VALKEY_URL="redis://valkey_server:6379/0"

# Neo4j Connection
NEO4J_URI="bolt://neo4j_server:7687"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="mysecretpassword" # Match the password in docker-compose.yml

# Ollama Hosts
OLLAMA_HOST="http://ollama:11434"
OLLAMA_EMBEDDING_HOST="http://ollama_embedding:11434"

# WhatsApp Credentials
WHATSAPP_VERIFY_TOKEN="your_super_secret_verify_token_from_meta"
PHONE_NUMBER_ID="your_whatsapp_phone_number_id_from_meta"

3. Set Up Secrets

Create a secrets/ directory in the root of the project. This directory is ignored by Git and Docker for security.

mkdir secrets

Create the following files inside the secrets/ directory:

postgres_secrets.txt: Contains the password for the postgres user.

whatsapp_token.txt: Contains your permanent or temporary WhatsApp Cloud API access token.

whatsapp_secrets.txt: Contains the App Secret from your Meta for Developers app dashboard, used for webhook signature verification.

4. Build and Run the Services

Use Docker Compose to build the images and start all the services. The --build flag is important on the first run.


docker-compose up --build -d


The first startup will be slow as Docker needs to download the base images and the Ollama models (qwen, nomic-embed-text, etc.). This can take several minutes.

Use docker-compose logs -f to monitor the logs of all services and ensure they start up correctly.

5. Populate the Databases

Once the containers are running, you need to populate the Neo4j Knowledge Graph and the PostgreSQL database.

a) Populate the Knowledge Graph (Neo4j):
Run the ingestion script. This command executes the script inside the running llm_service container.


docker-compose exec llm_service python -m utils.db.graph_builder

b) Populate the Relational Database (PostgreSQL):
Connect to the PostgreSQL container and run the SQL script.

docker-compose exec -T db_server psql -U postgres -d autoparts_db < utils/db/init_db.sql


This command pipes the contents of your local init_db.sql file directly into the psql client inside the container.

6. Test the Application

Web UI: Open your browser and navigate to http://localhost:8000. You should see the main web form.

Health Check: Visit http://localhost:8000/health to confirm the API is running.

Neo4j Browser: Visit http://localhost:7474 to access the Neo4j browser. Log in with neo4j and the password you set (mysecretpassword). You can run Cypher queries like MATCH (n) RETURN n LIMIT 25 to see your graph.

WhatsApp Webhook: Configure your Meta for Developers app to point its webhook to your public URL (using a tool like ngrok for local development: ngrok http 8000). Send a message to your WhatsApp number to test the end-to-end flow.

🔧 Maintenance & Further Development
Updating the Knowledge Base

To add more product information, you can:

Add new .csv or .txt files to the utils/data/ directory.

Update main.py to include the new file paths in the knowledge_base list.

Update the ingestion script utils/db/graph_builder.py to parse and load the new data into Neo4j.

Restart the application (docker-compose up --build -d) to re-trigger the data ingestion in the lifespan manager.

Changing LLM Models

Update the ollama pull command in docker-compose.yml.

Change the model name variables in utils/llm_tools.py and utils/image_processor.py.

Rebuild and restart the services.
