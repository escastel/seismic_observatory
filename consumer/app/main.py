"""Consumer entrypoint placeholder for the setup phase."""

import logging

from .config import ConsumerConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    """Load configuration; ETL is implemented in the Consumer story."""
    config = ConsumerConfig()
    logger.info("Consumer configured for topics %s/%s", config.raw_topic, config.replay_topic)


if __name__ == "__main__":
    main()
