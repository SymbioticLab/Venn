import asyncio
from evaluation.commons import *
from collections import deque
import random
import copy
import csv
import os

class Task_pool:
    def __init__(self, config):
        self.job_meta_list = deque()
        self.job_task_dict = {}
        self.config = config
        self.select_time = 0

    async def init_job(self, job_id: int, job_meta: dict):
        job_meta["job_id"] = job_id
        self.job_meta_list.append(job_meta)

        self.job_task_dict[job_id] = deque()
        test_task_meta = {
            "client_id": -1,
            "round": 0,
            "event": MODEL_TEST,
            "test_ratio": self.config["test_ratio"],
            "test_bsz": self.config["test_bsz"]
        }
        agg_test_meta = {
            "client_id": -1,
            "round": 0,
            "event": AGGREGATE_TEST,
        }
        self.job_task_dict[job_id].append(test_task_meta)
        self.job_task_dict[job_id].append(agg_test_meta)

        test_csv_file_name = f"./evaluation/monitor/executor/test_{job_id}_{self.config['sched_alg']}.csv"
        os.makedirs(os.path.dirname(test_csv_file_name), exist_ok=True)
        fieldnames = ["round", "cnt", "test_loss", "acc", "acc_5", "test_len"]
        with open(test_csv_file_name, "w", newline="") as test_csv:
            writer = csv.DictWriter(test_csv, fieldnames=fieldnames)
            writer.writeheader()

        train_csv_file_name = f"./evaluation/monitor/executor/train_{job_id}_{self.config['sched_alg']}.csv"
        os.makedirs(os.path.dirname(test_csv_file_name), exist_ok=True)
        fieldnames = ["round", "cnt", "moving_loss", "avg_moving_loss", "trained_size"]
        with open(train_csv_file_name, "w", newline="") as train_csv:
            writer = csv.DictWriter(train_csv, fieldnames=fieldnames)
            writer.writeheader()

    def _pop_failed_task(self, job_id: int, round: int):
        task_list = self.job_task_dict[job_id]
        while task_list:
            task = task_list.pop()
            if task["event"] == CLIENT_TRAIN and task["round"] == round:
                continue
            else:
                task_list.append(task)
                break
            
    async def insert_job_task(self, job_id: int, client_id: int, round: int, event: str, task_meta: dict):
        """event: {CLIENT_TRAIN, AGGREGATE, FINISH, ROUND_FAIL}
        """
        task_meta["client_id"] = client_id
        task_meta["round"] = round
        task_meta["event"] = event
        
        if job_id not in self.job_task_dict:
            return
        
        if event == ROUND_FAIL:
            self._pop_failed_task(job_id, round)

        test_task_meta = {
            "client_id": -1,
            "round": round,
            "event": MODEL_TEST,
            "test_ratio": self.config["test_ratio"],
            "test_bsz": self.config["test_bsz"]
        }
        
        agg_test_meta = {
            "client_id": -1,
            "round": round,
            "event": AGGREGATE_TEST,
        }
        
        if event == JOB_FINISH:
            self.job_task_dict[job_id].append(test_task_meta)
            self.job_task_dict[job_id].append(agg_test_meta)

        self.job_task_dict[job_id].append(task_meta)

        if event == AGGREGATE and round % self.config["eval_interval"] == 0:
            self.job_task_dict[job_id].append(test_task_meta)
            self.job_task_dict[job_id].append(agg_test_meta)


    async def get_next_task(self)->dict:
        """Get next task, prioritize previous job id if there is still task left for the job
        """
        job_num = len(self.job_meta_list)
        for _ in range(job_num):
            job_meta = copy.deepcopy(self.job_meta_list[0])
            job_id = job_meta["job_id"]
            if len(self.job_task_dict[job_id]) > 0 and self.select_time < 10:
                task_meta = self.job_task_dict[job_id].popleft()
                for key, value in task_meta.items():
                    if key == "client_id":
                        job_meta["client_id_list"] = [value]
                    else:
                        job_meta[key] = value

                if task_meta["event"] == CLIENT_TRAIN:
                    cnt = 1
                    while self.job_task_dict[job_id] and cnt < 5:
                        task_meta = self.job_task_dict[job_id].popleft()
                        if task_meta["event"] != job_meta["event"] or\
                            task_meta["round"] != job_meta["round"]:
                            self.job_task_dict[job_id].appendleft(task_meta)
                            break
                        job_meta["client_id_list"].append(task_meta["client_id"])
                        cnt += 1

                self.select_time += 1
                return job_meta
            
            self.select_time = 0
            self.job_meta_list.append(self.job_meta_list.popleft())
        return None
        
    async def remove_job(self, job_id: int):
        try:
            temp_deque = deque()
            while self.job_meta_list:
                job_meta = self.job_meta_list.popleft()
                if job_meta["job_id"] == job_id:
                    break
                temp_deque.append(job_meta)
            while temp_deque:
                self.job_meta_list.appendleft(temp_deque.pop())

            del self.job_task_dict[job_id]
        except:
            pass

    
    async def report_result(self, job_id: int, round: int, result: dict, is_train: bool = False):
        if not is_train:
            test_csv_file_name = f"./evaluation/monitor/executor/test_{job_id}_{self.config['sched_alg']}.csv"
            fieldnames = ["round", "cnt", "test_loss", "acc", "acc_5", "test_len"]
            os.makedirs(os.path.dirname(test_csv_file_name), exist_ok=True)
            with open(test_csv_file_name, mode="a", newline="") as test_csv:
                writer = csv.DictWriter(test_csv, fieldnames=fieldnames)
                result["round"] = round
                writer.writerow(result)

        else:
            train_csv_file_name = f"./evaluation/monitor/executor/train_{job_id}_{self.config['sched_alg']}.csv"
            os.makedirs(os.path.dirname(train_csv_file_name), exist_ok=True)
            fieldnames = ["round", "cnt", "moving_loss", "avg_moving_loss", "trained_size"]
            with open(train_csv_file_name, mode="a", newline="") as train_csv:
                writer = csv.DictWriter(train_csv, fieldnames=fieldnames)
                result["round"] = round
                writer.writerow(result)

