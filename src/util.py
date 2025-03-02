from collections import namedtuple


class Event:
    def __init__(self, time, type, obj_id, msg):
        self.time = time
        self.type = type
        self.obj_id = obj_id
        self.msg = msg # the type depend on type
    # override the comparison operator
    def __lt__(self, nxt):
        return self.time < nxt.time
        # TODO: sort by event as secondary

# Job: select, close
# client: assign, execute, finish


Request = namedtuple("Request", "duration amount fraction workload comm eligibility")
# AsyncRequest = namedtuple("AsyncRequest", "duration amount fraction workload comm eligibility")
