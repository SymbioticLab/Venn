"""FL Job Manager."""

from propius.controller.util import Msg_level, Propius_logger
from propius.controller.job_manager.job_manager import Job_manager
from propius.controller.channels import propius_pb2_grpc
from propius.controller.config import (
    PROPIUS_ROOT,
    PROPIUS_CONTROLLER_ROOT,
    GLOBAL_CONFIG_FILE,
)
import asyncio
import os
import yaml
import grpc

_cleanup_coroutines = []


async def serve(gconfig, logger):
    async def server_graceful_shutdown():
        logger.print(f"=====Job manager shutting down=====", Msg_level.WARNING)
        job_manager.jm_monitor.report()
        job_manager.job_db_portal.flushdb()

        try:
            heartbeat_task.cancel()
            plot_task.cancel()
            await heartbeat_task
            await plot_task
        except asyncio.exceptions.CancelledError:
            pass

        try:
            await job_manager.sched_channel.close()
        except Exception as e:
            logger.print(e, Msg_level.WARNING)
        await server.stop(5)

    server = grpc.aio.server()
    job_manager = Job_manager(gconfig, logger)
    propius_pb2_grpc.add_Job_managerServicer_to_server(job_manager, server)
    server.add_insecure_port(f"{job_manager.ip}:{job_manager.port}")
    await server.start()

    heartbeat_task = asyncio.create_task(job_manager.heartbeat_routine())
    plot_task = asyncio.create_task(job_manager.plot_routine())

    logger.print(
        f"server started, listening on {job_manager.ip}:{job_manager.port}",
        Msg_level.INFO,
    )
    _cleanup_coroutines.append(server_graceful_shutdown())

    await server.wait_for_termination()


def main():
    with open(GLOBAL_CONFIG_FILE, "r") as gyamlfile:
        try:
            gconfig = yaml.load(gyamlfile, Loader=yaml.FullLoader)
            log_file_path = (
                PROPIUS_ROOT / gconfig["log_path"] / "jm.log"
            )
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

            logger = Propius_logger(
                "job manager",
                log_file=log_file_path,
                verbose=gconfig["verbose"],
                use_logging=True,
            )

            logger.print(f"read config successfully", Msg_level.INFO)
            asyncio.run(serve(gconfig, logger))
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logger.print(e, Msg_level.ERROR)
        finally:
            asyncio.run(*_cleanup_coroutines)

if __name__ == "__main__":
    main()
