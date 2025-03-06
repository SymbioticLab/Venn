# Application Layer
## Defination
A job is an application running a federated computation workload. It should be an application that continuously interacts with `job_manager` in `propius_controller` and `propius_parameter_manager` across its lifetime. 
## Procedure
1. A job registers itself to `job_manager` in `propius_controller`, providing its network address and specifying its constraints on client attributes. The job could optionally provide its estimation for the total number of rounds and clients needed in the future. `job_manager` either accepts the registration, or reject it if the estimation is unrealistic (eg. too large). The estimations could be utilized by fair-queueing schedulers, and serve as an access control for later requests from this job.

2. The job initiates a new round, specifying the number of clients needed for this round. If current round number exceeds the original estimation, `job_manager` will reject this request and ask the job to register again. `job_manager` increments the job's `round` by 1, updates the `demand` field, and clears the `amount` field in job database (sets `amount` to be 0).
`scheduler` will coordinate this request with other requests, and create an allocation plan according to its policy. `client_manager` will bind clients based on the plan, while enforcing end-to-end constraints.
At this moment, the job may start transmitting the round parameters to `propius_parameter_manager`, to be fetched by binded clients.

3. `job_manager` stops allocating clients to the job, if either (1) the job sends an `end_request` indicating sufficient number of clients have been attained, or (2) the attained client `amount` has reached the round `demand`. The execution phase begins.

4. Allocate clients fetch model weights from `propius_parameter_manager`, and conduct local execution. Finally, individual client will report back execution results to `propius_parameter_manager`.

5. After desired amount of results have been received by `propius_parameter_manager`, or there is a timeout due to insufficient responses, `propius_parameter_manager` informs the job the round result. The job will either decide to finish (6), or initiate a new round of request (2).

6. The job sends a finish message. Its parameters and metadata will then be deleted by `Propius`.


## Job database
### Schema
This is the metadata for every job. We use Redis JSON key-value store, where key is the `job_id`.
|Field Name|Data Type|Description| 
|--|--|--|
|timestamp | numeric | job register time|
|total_sched | numeric | total time spent in waiting for clients|
|start_sched | numeric | last timestamp when the job starts a new round|
|job_ip | text | IP address of the job |
|port | numeric | port number |
|total_demand | numeric | total number of clients estimated |
|total_round| numeric | total number of rounds estimated |
|attained_service | numeric | total number of clients attained |
|round | numeric | round number |
|demand | numeric | number of clients needed in this round |
|amount| numeric| number of clients attained in this round |
|score | numeric| priority score|
|public_constraint.[x]| numeric | lower bound for client public attribute value for constraint x |
|private_constraint.[y]| numeric | lower bound for client private attribute value for constraint y |

## Job lifetime
- Job will be removed if runtime is greater than JOB_EXPIRE_TIME
- Job will be removed if time intervals is greater than JOB_MAX_SILENT_TIME
- If use policy that removes job after reaching the estimated round
    - If job provides total round estimation $r_{total}$
        - Job will be removed after $r_{total}$ 
    - Job does not provide total round estimation
        - Job will be removed after MAX_ROUND