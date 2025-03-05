```Python
import amg
import fedscale

# Define model
model = ...
loss_fn = ...
aggregator = ...
optimizer = ...
learning_rate = ...
lr_scheduler = ...
round_num = ...
# Define constraint
constraints = { 'cpu': 72,
                'memory': 4,
                'os': 10.5,
                'dataset':100,
                ...}
# Define client 
client = amg.Client(constraints, demand=10)
# Define client update handler
def client_update_handler(client_response):
    # optional operation on client parameter update
    return client_response
# Create job object
fl_job = amg.Job(model, loss_fn, aggregator, optimizer, 
                learning_rate, lr_scheduler, client,
                client_update_handler)
# Initiate the training process
fl_job.register()

def train():
    for r in range (round_num):
        # Initiate a round
        fl_job.request()
        print(f"Round {r}: Recieve {fl_job.num_client} clients' update")
        # amg.Job will handle training plan dispatch upon client check in
        # client_update_handler can be defined for optional operation on client's update, invoked upon client respond
        fl_job.print_stats()
    fl_job.complete_job()

train()
```