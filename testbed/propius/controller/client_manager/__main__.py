"""FL Client Manager"""

import sys
import os
from propius.controller.util import Msg_level, Propius_logger
from propius.controller.client_manager.client_manager import Client_manager
from propius.controller.channels import propius_pb2_grpc
from propius.controller.config import (
    PROPIUS_ROOT,
    PROPIUS_CONTROLLER_ROOT,
    GLOBAL_CONFIG_FILE,
)
import yaml
import grpc
import asyncio
import click

_cleanup_coroutines = []


async def serve(gconfig, cm_id: int, logger: Propius_logger):
    async def server_graceful_shutdown():
        logger.print(f"=====Client manager shutting down=====", Msg_level.WARNING)
        client_manager.cm_monitor.report(client_manager.cm_id)
        client_manager.client_db_portal.flushdb()
        if client_manager.sched_mode == "offline":
            client_manager.temp_client_db_portal.flushdb()
        try:
            client_assign_task.cancel()
            plot_task.cancel()
            await plot_task
        except asyncio.exceptions.CancelledError:
            pass

        try:
            if client_manager.sched_mode == "offline":
                await client_manager.sched_channel.close()
        except Exception as e:
            logger.print(e, Msg_level.WARNING)

        await client_assign_task
        await server.stop(5)

    server = grpc.aio.server()
    client_manager = Client_manager(gconfig, cm_id, logger)
    propius_pb2_grpc.add_Client_managerServicer_to_server(client_manager, server)
    server.add_insecure_port(f"{client_manager.ip}:{client_manager.port}")
    _cleanup_coroutines.append(server_graceful_shutdown())
    await server.start()

    client_assign_task = asyncio.create_task(client_manager.client_assign_routine())
    plot_task = asyncio.create_task(client_manager.plot_routine())
    logger.print(
        f"server started, listening on {client_manager.ip}:{client_manager.port}",
        Msg_level.INFO,
    )
    await server.wait_for_termination()


@click.command()
@click.argument("cm_id", type=int)
def main(cm_id):
    with open(GLOBAL_CONFIG_FILE, "r") as gyamlfile:
        try:
            gconfig = yaml.load(gyamlfile, Loader=yaml.FullLoader)

            log_file_path = (
                PROPIUS_ROOT
                / gconfig["log_path"]
                / f"cm_{cm_id}.log"
            )
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
            logger = Propius_logger(
                f"client manager {cm_id}",
                log_file=log_file_path,
                verbose=gconfig["verbose"],
                use_logging=True,
            )
            logger.print(f"read config successfully", Msg_level.INFO)
            asyncio.run(serve(gconfig, cm_id, logger))
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logger.print(e, Msg_level.ERROR)
        finally:
            asyncio.run(*_cleanup_coroutines)

if __name__ == "__main__":
    main()
