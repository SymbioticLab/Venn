# Scheduling Layer
## Overview
Scheduling layer sits beneath the application layer. The scheduling logic is triggered by: (1) new job registeration, (2) existing jobs' new request, (3) `client_manager` sends a periodic update request. There are two forms of scheduling logic implemented: (1) online scheduling and (2) offline scheduling.

## Metadata for scheduling
Job Metadata:
- registration timestamp, time spent in being scheduled, last scheduling start time, current time elapse $t$
- job IP
- total allocation in past rounds $d_a$, current round number $r$, current demand $d$, current allocation amount
- total demand estimated $d_{total}$, total round estimated $r_{total}$, remaining demand estimated $d_r$, remaining time estimated $t_r$ 
    -  If job provides total round estimation $r_{total}$
        - $d_{total} = d_a + (r_{total} - r) \times d$
        - $d_r = d_{total} - d_a$
        - $t_r = t / r \times (r_{total} - r)$
    - If job does not provide total round estimation
        - $r_{total} = 2 \times r$
        - $d_{total} = 2 \times d_a$
        - $d_r = d_{total} - d_a$
        - $t_r = 2 \times t$
- public constraints, private constraints

Client Metadata:
- public attributes
- client IP
- client performance in last rounds (eg. speed)
- past client attribute distribution


## Online scheduling
As the client resources are highly dynamic, it is difficult to keep track of every available client resources long-term, which involves constant state checking and updates. It is therefore more appropiate to remove any state for client resources, and assign tasks to clients whenever they are available in an online fashion.

The online `scheduler` in `propius_controller` sets a score for every outstanding job based on its metadata (by interfacing with `job_db`). `client_manager` in `propius_controller` searches for an outstanding job with the highest score for every client check-in, and assign a job to an eligible client.

The online scheduling logic is invoked by either new job registration or new job request.

This is an example of a FIFO scheduler.
```python
class FIFO_scheduler(Scheduler):
    # class attributes initialization
    
    async def online(self, job_id: int):
        """Give every job which doesn't have a score yet a score of -timestamp

        Args:
            job_id: job id
        """
        
        job_timestamp = float(self.job_db_portal.get_field(job_id, "timestamp"))

        score = - (job_timestamp - self.start_time)
        self.job_db_portal.set_score(score, job_id)
```

## Offline
Though online scheduling minizes state management for ephemeral resources over the network, it has several limitations, just to mention a few: (1) enforcing a priority for every job under the same scale, which is difficult to calculate for complex scheduling policy (2) making quick selection decisions under a local view upon client check-in (3) difficult to coordinate between clients. Therefore, we uses a temporary client database to cache active client resources (with a ttl), and batch-process client-to-job binding process.

Offline `scheduler` maintains a `job_group` data structure, which comprises of several job groups, and their corresponding conditions, which specify a coarse client subset. `client_manager` will aynchronously ping `scheduler` for this `job_group` update, and `scheduler` should return this data structure back to `client_manager`. `client_manager` will then enforce the coarse group condition, pairing a job group to an active client subset, as well as ensuring end-to-end constraint satisfaction. Clients will asynchronously ping `client_manager`, looking up the `temp_client_db` for binded jobs (tasks).

This is an example of an offline FIFO scheduler.
```python
class FIFO_scheduler(Scheduler):
    def __init__(self, gconfig: dict, logger: Propius_logger):
        super().__init__(gconfig, logger)
        # only one group
        self.job_group.insert_key(0)
        q = ""
        for name in self.public_constraint_name:
            q += f"@{name}: [-inf +inf] "
        self.job_group[0].insert_condition_and(q)

    async def job_regist(self, job_id: int):
        job_list = self.job_group.get_job_group(0)
        updated_job_list = list(filter(lambda x: self.job_db_portal.exist(x), job_list))
        updated_job_list.append(job_id)
        self.job_group.set_job_group(0, updated_job_list)

    async def job_request(self, job_id: int):
        pass

```

This is an example of a group condition.
```python
condition = "@CPU:[0 10], @MEM:[300 500]"
```

