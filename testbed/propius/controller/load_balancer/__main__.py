"""Distributor of client traffics to client managers."""

from propius.controller.util import Msg_level, Propius_logger
from propius.controller.load_balancer.load_balancer import Load_balancer
from propius.controller.channels import propius_pb2_grpc
from propius.controller.config import (
    PROPIUS_ROOT,
    PROPIUS_CONTROLLER_ROOT,
    GLOBAL_CONFIG_FILE,
)
import yaml
import grpc
import asyncio
import os

_cleanup_coroutines = []


async def serve(gconfig, logger):
    async def server_graceful_shutdown():
        logger.print(f"=====Load balancer shutting down=====", Msg_level.WARNING)
        load_balancer.lb_monitor.report()

        try:
            plot_task.cancel()
            await plot_task
        except asyncio.exceptions.CancelledError:
            pass

        await load_balancer._disconnect_cm()
        await server.stop(5)

    server = grpc.aio.server()
    load_balancer = Load_balancer(gconfig, logger)
    propius_pb2_grpc.add_Load_balancerServicer_to_server(load_balancer, server)
    server.add_insecure_port(f"{load_balancer.ip}:{load_balancer.port}")
    _cleanup_coroutines.append(server_graceful_shutdown())
    await server.start()
    logger.print(
        f"server started, listening on {load_balancer.ip}:{load_balancer.port}",
        Msg_level.INFO,
    )
    plot_task = asyncio.create_task(load_balancer.plot_routine())

    await server.wait_for_termination()


def main():
    with open(GLOBAL_CONFIG_FILE, "r") as gyamlfile:
        try:
            gconfig = yaml.load(gyamlfile, Loader=yaml.FullLoader)
            log_file_path = (
                PROPIUS_ROOT / gconfig["log_path"] / "lb.log"
            )
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
            logger = Propius_logger(
                "load balancer",
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
