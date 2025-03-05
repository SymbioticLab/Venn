from datetime import datetime
from enum import Enum
import logging
import logging.handlers
from propius.controller.config import GLOBAL_CONFIG_FILE
import yaml

def get_time() -> str:
    current_time = datetime.now()
    format_time = current_time.strftime("%Y-%m-%d:%H:%M:%S:%f")[:-4]
    return format_time


def geq(t1: tuple, t2: tuple) -> bool:
    """Compare two tuples. Return True only if every values in t1 is greater or equal than t2

    Args:
        t1
        t2
    """

    for idx in range(len(t1)):
        if t1[idx] < t2[idx]:
            return False
    return True


def gt(t1: tuple, t2: tuple) -> bool:
    """Compare two tuples. Return True only if every values in t1 is greater than t2

    Args:
        t1
        t2
    """

    for idx in range(len(t1)):
        if t1[idx] < t2[idx]:
            return False
    if t1 == t2:
        return False
    return True


class Msg_level(Enum):
    PRINT = 0
    DEBUG = 1
    INFO = 2
    WARNING = 3
    ERROR = 4


CPU_F = "cpu_f"
RAM = "ram"
FP16_MEM = "fp16_mem"
ANDROID_OS = "android_os"
DATASET_SIZE = "dataset_size"


def encode_specs(**kargs) -> tuple[list, list]:
    """Encode client specs. Eg. encode_specs(CPU_F=18, RAM=8).

    Args:
        Keyword arguments

    Raises:
        ValueError: if input key is not recognized
    """
    with open(GLOBAL_CONFIG_FILE, "r") as gyamlfile:
        gconfig = yaml.load(gyamlfile, Loader=yaml.FullLoader)
        public_spec = gconfig["job_public_constraint"]
        private_spec = gconfig["job_private_constraint"]

    public_spec_dict = {}
    private_spec_dict = {}

    for key in public_spec:
        if key in kargs:
            public_spec_dict[key] = kargs[key]
        else:
            public_spec_dict[key] = 0

    for key in private_spec:
        if key in kargs:
            private_spec_dict[key] = kargs[key]
        else:
            private_spec_dict[key] = 0

    for key in kargs.keys():
        if key not in public_spec and key not in private_spec:
            raise ValueError(f"{key} spec is not supported")

    # TODO encoding, value check

    return (list(public_spec_dict.values()), list(private_spec_dict.values()))


class Propius_logger:
    def __init__(
        self,
        actor: str,
        log_file: str = None,
        verbose: bool = True,
        use_logging: bool = True,
    ):
        self.verbose = verbose
        self.use_logging = use_logging
        self.actor = actor
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

    def print(self, message: str, level: int = Msg_level.PRINT):
        message = f"{self.actor}: {message}"
        if self.verbose:
            print(f"{get_time()} {message}")
        if self.use_logging:
            if level == Msg_level.DEBUG:
                self.logger.debug(message)
            elif level == Msg_level.INFO:
                self.logger.info(message)
            elif level == Msg_level.WARNING:
                self.logger.warning(message)
            elif level == Msg_level.ERROR:
                self.logger.error(message)


class Group_condition:
    def __init__(self):
        # a list of condition
        self.condition_list = ""

    def insert_condition_and(self, condition: str):
        self.condition_list += f" ({condition}) "

    def insert_condition_or(self, condition: str):
        self.condition_list += f" | ({condition}) "

    def str(self) -> str:
        return self.condition_list

    def clear(self):
        self.condition_list = ""


class Job_group:
    def __init__(self):
        self.key_list = []
        self.key_job_group_map = {}
        self.key_group_condition_map = {}

    def insert_key(self, key):
        if key not in self.key_list:
            self.key_list.append(key)
            self.key_job_group_map[key] = []
            self.key_group_condition_map[key] = Group_condition()

    def remove_key(self, key):
        if key in self.key_list:
            self.key_list.remove(key)
            del self.key_job_group_map[key]
            del self.key_group_condition_map[key]

    def clear_group_info(self):
        for key in self.key_list:
            self.key_job_group_map[key].clear()
            self.key_group_condition_map[key].clear()

    def __getitem__(self, key) -> Group_condition:
        return self.key_group_condition_map.get(key)

    def __setitem__(self, key, value: Group_condition):
        self.key_group_condition_map[key] = value

    def set_job_group(self, key, job_group: list):
        if key in self.key_list:
            self.key_job_group_map[key] = job_group

    def get_job_group(self, key) -> list:
        if key in self.key_list:
            return self.key_job_group_map[key]

    def __repr__(self):
        str = ""
        for key in self.key_list:
            str += f"{key} - {self.key_job_group_map[key]} - {self.key_group_condition_map[key]}\n"

        return str
