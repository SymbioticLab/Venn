import heapq
from collections import Counter, defaultdict

class JobGroup():
    def __init__(self, eligibility_index ):
        self.eligibility_index = eligibility_index
        self.job_list = []
        self.job_set = set()

    def add_job(self, job, demand):
        # assume there is no jobs with same id in the group
        if job not in self.job_set:
            heapq.heappush(self.job_list, (demand, job))
            self.job_set.add(job)

    def remove_job(self, job_id):
        for i, (demand, id) in enumerate(self.job_list):
            if id == job_id:
                # Remove it from the list
                self.job_list.pop(i)
                heapq.heapify(self.job_list)
                self.job_set.remove(job_id)
                break

    @property
    def queue_len(self):
        return len(self.job_list)

    @property
    def demand_list(self):
        return sorted(demand for demand, _ in self.job_list)

class IRS():
    def __init__(self):
        self.job_group_list = {}
        self.allocation_plan = {}

    def _add_job_group(self, eligibility_index):
        if eligibility_index not in self.job_group_list:
            self.job_group_list[eligibility_index] = JobGroup(eligibility_index)

    def add_request(self, job_id, demand, eligibility_index):
        self._add_job_group(eligibility_index)
        self.job_group_list[eligibility_index].add_job(job_id, demand)

    def remove_request(self, job_id, eligibility_index):
        if eligibility_index not in self.job_group_list:
            return
        self.job_group_list[eligibility_index].remove_job(job_id)
        if self.job_group_list[eligibility_index].queue_len == 0:
            self.job_group_list.pop(eligibility_index)

    def _get_affected_queuing_len(self, demand_list, res_list, target_demand_list, target_res_list):
        # Assert all input is non-empty
        original_delay = self._get_queuing_delay(demand_list, res_list)
        target_delay = self._get_queuing_delay(target_demand_list, target_res_list)
        if original_delay <= target_delay:
            return len(demand_list)
        else:
            delay_sum = 0
            for i, d in enumerate(demand_list):
                delay_sum += d / res_list[i]
                if delay_sum >= target_delay:
                    return i
        return len(demand_list)

    def _get_queuing_delay(self, demand_list, allocate_res):
        return sum([demand / res for demand, res in zip(demand_list, allocate_res)])

    def schedule_first_request_per_group(self, checkin_client):
        # sort job group by raw resource size
        # calculate initial resource allocation
        flat_data = [item for sublist in checkin_client if sublist for item in sublist]
        count_dict = Counter(flat_data)
        sorted_eli_list = sorted(count_dict.items(), key=lambda x: x[1])
        init_allocation_num = {}
        init_allocation_set = defaultdict(set)
        tmp_checkin_client = checkin_client.copy()

        # start with the job group with smallest eligible resources
        for e_id, _ in sorted_eli_list:
            init_clt = 0
            to_remove = []
            for clt in tmp_checkin_client:
                if e_id in clt :
                    init_clt += 1
                    to_remove.append(clt)
                    init_allocation_set[e_id].add(tuple(clt))
            for clt in to_remove:
                tmp_checkin_client.remove(clt)
            init_allocation_num[e_id] = max(1, init_clt)
        # print("Initial allocation plan: ",init_allocation_num)

        queuing_len_dict = {id: self.job_group_list[id].queue_len for id in self.job_group_list}
        group_demand_list = {id: self.job_group_list[id].demand_list for id in self.job_group_list}
        group_demand_res_list = {id: [init_allocation_num[id] if id in init_allocation_num else 0 for _ in range(queuing_len_dict[id])]  for id in self.job_group_list}

        sorted_eli_list = sorted(count_dict.items(), key=lambda x: x[1], reverse = True)
        # print(">>>> Queue length: ", queuing_len_dict)
        for sorted_id, (eid, _ ) in enumerate(sorted_eli_list):
            # pick the first job in the group
            if eid in queuing_len_dict and queuing_len_dict[eid] > 0 and init_allocation_num[eid] > 0:
                for i in range(sorted_id+1, len(sorted_eli_list)):
                    compare_eid = sorted_eli_list[i][0]
                    if compare_eid not in queuing_len_dict or queuing_len_dict[compare_eid] == 0:
                        init_allocation_num[eid] += init_allocation_num[compare_eid]
                        init_allocation_set[eid] = init_allocation_set[eid].union(init_allocation_set[compare_eid])
                        continue

                    current_affected_queuing_len = self._get_affected_queuing_len(group_demand_list[eid] , group_demand_res_list[eid],
                                                                                  group_demand_list[compare_eid], group_demand_res_list[compare_eid])
                    # print(f"Current affected queuing length: {current_affected_queuing_len} v.s. {queuing_len_dict[eid]}")

                    if  init_allocation_num[compare_eid] > 0 and\
                            current_affected_queuing_len / init_allocation_num[eid] > queuing_len_dict[compare_eid] / init_allocation_num[compare_eid]:
                        init_allocation_num[eid] += init_allocation_num[compare_eid]
                        queuing_len_dict[eid] += queuing_len_dict[compare_eid]
                        init_allocation_set[eid] = init_allocation_set[eid].union(init_allocation_set[compare_eid])
                        group_demand_list[eid] = group_demand_list[eid] + group_demand_list[compare_eid]
                        group_demand_res_list[eid] = [res + init_allocation_num[compare_eid] for res in group_demand_res_list[eid]] + group_demand_res_list[compare_eid]

                        init_allocation_num[compare_eid] = 0
                        init_allocation_set[compare_eid] = set()
                        group_demand_list[compare_eid] = []
                        group_demand_res_list[compare_eid] = []

                    else:
                        break
            else:
                init_allocation_set[eid] = set()
                init_allocation_num[eid] = 0
        self.allocation_plan = init_allocation_set
        print("Final allocation plan: ", init_allocation_set)
        return init_allocation_set

    def schedule_task(self, client_eli):
        for group in self.allocation_plan:
            if tuple(client_eli) in self.allocation_plan[group] and group in self.job_group_list and self.job_group_list[group].queue_len > 0:
                return [id for _, id in self.job_group_list[group].job_list]
        return []




