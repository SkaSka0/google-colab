import logging

def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s %(message)s",
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger("colab_fetcher")

logger = setup_logger() 
