"""Root parameter server."""

from propius.parameter_server.util import Msg_level, Propius_logger
from propius.parameter_server.channels import (
    parameter_server_pb2,
    parameter_server_pb2_grpc,
)
from propius.parameter_server.config import (
    PROPIUS_PARAMETER_SERVER_ROOT,
    PROPIUS_ROOT,
    GLOBAL_CONFIG_FILE,
)
from propius.parameter_server.root.parameter_server import Parameter_server
import yaml
import grpc
import asyncio
import os

_cleanup_coroutines = []


async def serve(gconfig, logger):
    async def server_graceful_shutdown():
        await server.stop(5)
        try:
            clock_evict_routine.cancel()
            await clock_evict_routine
        except asyncio.exceptions.CancelledError:
            pass

    channel_options = [
        ("grpc.max_receive_message_length", gconfig["max_message_length"]),
        ("grpc.max_send_message_length", gconfig["max_message_length"]),
    ]

    server = grpc.aio.server(options=channel_options)
    root_ps = Parameter_server(gconfig, logger)

    parameter_server_pb2_grpc.add_Parameter_serverServicer_to_server(root_ps, server)
    server.add_insecure_port(f"{gconfig['root_ps_ip']}:{gconfig['root_ps_port']}")
    _cleanup_coroutines.append(server_graceful_shutdown())

    await server.start()

    clock_evict_routine = asyncio.create_task(root_ps.clock_evict_routine())
    logger.print(
        f"server started, listening on {gconfig['root_ps_ip']}:{gconfig['root_ps_port']}",
        Msg_level.INFO,
    )
    await server.wait_for_termination()


def main():
    with open(GLOBAL_CONFIG_FILE, "r") as gyamlfile:
        try:
            gconfig = yaml.load(gyamlfile, Loader=yaml.FullLoader)
            log_file_path = PROPIUS_ROOT / gconfig["log_path"] / "root_ps.log"

            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

            logger = Propius_logger(
                "root_ps",
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
