"""Producer entrypoint placeholder for the setup phase."""

import logging

from .config import ProducerConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    """Load configuration; ingestion is implemented in the Producer story."""
    config = ProducerConfig()
    logger.info("Producer configured for topic %s", config.raw_topic)


if __name__ == "__main__":
    main()
