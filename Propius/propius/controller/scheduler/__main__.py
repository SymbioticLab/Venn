"""Job scheduler."""

from propius.controller.util import Msg_level, Propius_logger
from propius.controller.channels import propius_pb2_grpc
from propius.controller.config import (
    PROPIUS_ROOT,
    PROPIUS_CONTROLLER_ROOT,
    GLOBAL_CONFIG_FILE,
)
import asyncio
import yaml
import grpc
import os

_cleanup_coroutines = []


async def serve(gconfig, logger):
    async def server_graceful_shutdown():
        logger.print("=====Scheduler shutting down=====", Msg_level.WARNING)
        scheduler.sc_monitor.report()

        try:
            plot_task.cancel()
            await plot_task
        except asyncio.exceptions.CancelledError:
            pass

        await server.stop(5)

    server = grpc.aio.server()

    sched_alg = gconfig["sched_alg"]
    sched_mode = gconfig["sched_mode"]

    if sched_mode == "online":
        if sched_alg == "fifo":
            from propius.controller.scheduler.online_module.fifo_scheduler import (
                FIFO_scheduler as Scheduler,
            )
        elif sched_alg == "random":
            from propius.controller.scheduler.online_module.random_scheduler import (
                Random_scheduler as Scheduler,
            )
        elif sched_alg == "srsf":
            from propius.controller.scheduler.online_module.srsf_scheduler import (
                SRSF_scheduler as Scheduler,
            )
        else:
            from propius.controller.scheduler.online_module.base_scheduler import (
                Scheduler,
            )
    elif sched_mode == "offline":
        if sched_alg == "fifo":
            from propius.controller.scheduler.offline_module.fifo_scheduler import (
                FIFO_scheduler as Scheduler,
            )
        elif sched_alg == "irs":
            from propius.controller.scheduler.offline_module.irs_scheduler import (
                IRS_scheduler as Scheduler,
            )
        else:
            from propius.controller.scheduler.offline_module.base_scheduler import (
                Scheduler,
            )

    scheduler = Scheduler(gconfig, logger)
    propius_pb2_grpc.add_SchedulerServicer_to_server(scheduler, server)
    server.add_insecure_port(f"{scheduler.ip}:{scheduler.port}")
    await server.start()

    plot_task = asyncio.create_task(scheduler.plot_routine())

    logger.print(
        f"server started, listening on {scheduler.ip}:{scheduler.port}, running {gconfig['sched_alg']}",
        Msg_level.INFO,
    )
    _cleanup_coroutines.append(server_graceful_shutdown())
    await server.wait_for_termination()


def main():
    with open(GLOBAL_CONFIG_FILE, "r") as gyamlfile:
        try:
            gconfig = yaml.load(gyamlfile, Loader=yaml.FullLoader)
            log_file_path = (
                PROPIUS_ROOT / gconfig["log_path"] / "sc.log"
            )
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
            logger = Propius_logger(
                "scheduler",
                log_file=log_file_path,
                verbose=gconfig["verbose"],
                use_logging=True,
            )
            logger.print(f"read config successfully")
            asyncio.run(serve(gconfig, logger))
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logger.print(e, Msg_level.ERROR)
        finally:
            asyncio.run(*_cleanup_coroutines)

if __name__ == "__main__":
    main()
