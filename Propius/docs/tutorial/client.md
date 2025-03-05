```Python
import amg_client
import time

fl_client = amg_client.Client()

def pick_task(task_offer:list)->int:
    ...

def participate():
    # Get task offer
    task_offer = fl_client.checkin()
    if not task_offer:
        return
    # Selected the best fit task for training
    selected_task = pick_task(task_offer)
    # Ask for training plan from job server
    plan = fl_client.request_plan(selected_task)
    # Perform local training on the selected task
    model_update = fl_client.train(plan)
    # Report update
    fl_client.report(model_update)

while True:
    # Check device condition
    if fl_client.available():
        participate()
    else:
        time.sleep(60)
```