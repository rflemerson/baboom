import logging

from dotenv import load_dotenv

from agents.flows.main_flow import product_ingestion_flow

load_dotenv()

logger = logging.getLogger(__name__)


def run_batch(count=5):
    """
    Thin wrapper to run the ingestion flow in batch from the CLI.
    """
    logger.info(f"--- Starting Batch Ingestion of {count} items ---")
    product_ingestion_flow(batch_size=count)
    logger.info("--- Batch Finished ---")


if __name__ == "__main__":
    run_batch(5)
