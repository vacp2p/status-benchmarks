import logging
import logging.config
import pathlib
import yaml

class TraceLogger(logging.Logger):
    TRACE = 5
    def trace(self, msg, *args, **kwargs) -> None:
        self.log(self.TRACE, msg, *args, **kwargs)

# Register level name and custom class BEFORE dictConfig/getLogger
logging.addLevelName(TraceLogger.TRACE, "TRACE")
logging.setLoggerClass(TraceLogger)

# Load YAML config
with open(pathlib.Path(__file__).parent.resolve() / 'logger_config.yaml', 'r') as f:
    config = yaml.safe_load(f)
    logging.config.dictConfig(config)
