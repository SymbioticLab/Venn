import logging
import logging.handlers

# Define Basic FL Events
UPDATE_MODEL = "update_model"
MODEL_TEST = "model_test"
SHUT_DOWN = "shut_down"
# START_ROUND = 'start_round'
# CLIENT_CONNECT = 'client_connect'
CLIENT_TRAIN = "client_train"
DUMMY_EVENT = "dummy_event"
UPLOAD_MODEL = "upload_model"
AGGREGATE = "aggregate"
AGGREGATE_TEST = "agg_test"
ROUND_FAIL = "round_fail"
JOB_FINISH = "finish"

# PLACEHOLD
DUMMY_RESPONSE = "N"

# TENSORFLOW = 'tensorflow'
# PYTORCH = 'pytorch'

JOB_META = {
    "model": "",
    "dataset": "",
}

TASK_META = {
    "client_id": -1,
    "round": -1,
    "event": "",
    "local_steps": 0,
    "learning_rate": 0,
    "batch_size": 0,
    "test_ratio": 0,
    "test_bsz": 0,
    "num_loaders": 5,
    "loss_decay": 0.9,
}

EXECUTE_META = JOB_META.update(TASK_META)

result_dict = {
    "accuracy": 0,
    "loss": 0,
    # training==
    "moving_loss": 0,
    "trained_size": 0,
}

out_put_class = {
    "Mnist": 10,
    "cifar10": 10,
    "imagenet": 1000,
    "emnist": 47,
    "amazon": 5,
    "openImg": 596,
    "google_speech": 35,
    "femnist": 62,
    "yelp": 5,
    "inaturalist": 1010,
}

MAX_MESSAGE_LENGTH = 1 * 1024 * 1024 * 1024  # 1GB


from datetime import datetime


def get_time() -> str:
    current_time = datetime.now()
    format_time = current_time.strftime("%Y-%m-%d:%H:%M:%S:%f")[:-4]
    return format_time


PRINT = 0
DEBUG = 1
INFO = 2
WARNING = 3
ERROR = 4

verbose = True


class My_logger:
    def __init__(
        self, log_file: str = None, verbose: bool = False, use_logging: bool = True
    ):
        self.verbose = verbose
        self.use_logging = logging
        if self.use_logging:
            if not log_file:
                raise ValueError("Empty log file")

            handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=5000000, backupCount=5
            )

            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)

            self.logger = logging.getLogger("mylogger")
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def print(self, message: str, level: int = PRINT):
        if self.verbose or level > INFO:
            print(f"{get_time()} {message}")

        if self.use_logging:
            if level == DEBUG:
                self.logger.debug(message)
            elif level == INFO:
                self.logger.info(message)
            elif level == WARNING:
                self.logger.warning(message)
            elif level == ERROR:
                self.logger.error(message)


def custom_print(message: str, level: int = PRINT):
    if level >= PRINT:
        print(f"{get_time()} {message}")

    if level == DEBUG:
        logging.debug(message)
    elif level == INFO:
        logging.info(message)
    elif level == WARNING:
        logging.warning(message)
    elif level == ERROR:
        logging.error(message)


def get_model_size(model_name, dataset_name):
    import pickle
    import sys

    if model_name == "resnet18":
        from evaluation.internal.models.specialized.resnet_speech import resnet18

        model = resnet18(num_classes=out_put_class[dataset_name], in_channels=1)
    elif model_name == "mobilenet_v2":
        from evaluation.internal.models.specialized.resnet_speech import mobilenet_v2

        model = mobilenet_v2(num_classes=out_put_class[dataset_name])

    model_size = sys.getsizeof(pickle.dumps(model)) / 1024.0 * 8.0  # kbits
    return model_size


if __name__ == "__main__":
    print(get_model_size("mobilenet_v2", "femnist"))
