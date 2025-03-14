# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

import propius.parameter_server.channels.parameter_server_pb2 as parameter__server__pb2


class Parameter_serverStub(object):
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.CLIENT_GET = channel.unary_unary(
            "/propius_parameter_server.Parameter_server/CLIENT_GET",
            request_serializer=parameter__server__pb2.job.SerializeToString,
            response_deserializer=parameter__server__pb2.job.FromString,
        )
        self.CLIENT_PUSH = channel.unary_unary(
            "/propius_parameter_server.Parameter_server/CLIENT_PUSH",
            request_serializer=parameter__server__pb2.job.SerializeToString,
            response_deserializer=parameter__server__pb2.ack.FromString,
        )
        self.JOB_PUT = channel.unary_unary(
            "/propius_parameter_server.Parameter_server/JOB_PUT",
            request_serializer=parameter__server__pb2.job.SerializeToString,
            response_deserializer=parameter__server__pb2.ack.FromString,
        )
        self.JOB_GET = channel.unary_unary(
            "/propius_parameter_server.Parameter_server/JOB_GET",
            request_serializer=parameter__server__pb2.job.SerializeToString,
            response_deserializer=parameter__server__pb2.job.FromString,
        )
        self.JOB_DELETE = channel.unary_unary(
            "/propius_parameter_server.Parameter_server/JOB_DELETE",
            request_serializer=parameter__server__pb2.job.SerializeToString,
            response_deserializer=parameter__server__pb2.ack.FromString,
        )


class Parameter_serverServicer(object):
    """Missing associated documentation comment in .proto file."""

    def CLIENT_GET(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Method not implemented!")
        raise NotImplementedError("Method not implemented!")

    def CLIENT_PUSH(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Method not implemented!")
        raise NotImplementedError("Method not implemented!")

    def JOB_PUT(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Method not implemented!")
        raise NotImplementedError("Method not implemented!")

    def JOB_GET(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Method not implemented!")
        raise NotImplementedError("Method not implemented!")

    def JOB_DELETE(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Method not implemented!")
        raise NotImplementedError("Method not implemented!")


def add_Parameter_serverServicer_to_server(servicer, server):
    rpc_method_handlers = {
        "CLIENT_GET": grpc.unary_unary_rpc_method_handler(
            servicer.CLIENT_GET,
            request_deserializer=parameter__server__pb2.job.FromString,
            response_serializer=parameter__server__pb2.job.SerializeToString,
        ),
        "CLIENT_PUSH": grpc.unary_unary_rpc_method_handler(
            servicer.CLIENT_PUSH,
            request_deserializer=parameter__server__pb2.job.FromString,
            response_serializer=parameter__server__pb2.ack.SerializeToString,
        ),
        "JOB_PUT": grpc.unary_unary_rpc_method_handler(
            servicer.JOB_PUT,
            request_deserializer=parameter__server__pb2.job.FromString,
            response_serializer=parameter__server__pb2.ack.SerializeToString,
        ),
        "JOB_GET": grpc.unary_unary_rpc_method_handler(
            servicer.JOB_GET,
            request_deserializer=parameter__server__pb2.job.FromString,
            response_serializer=parameter__server__pb2.job.SerializeToString,
        ),
        "JOB_DELETE": grpc.unary_unary_rpc_method_handler(
            servicer.JOB_DELETE,
            request_deserializer=parameter__server__pb2.job.FromString,
            response_serializer=parameter__server__pb2.ack.SerializeToString,
        ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
        "propius_parameter_server.Parameter_server", rpc_method_handlers
    )
    server.add_generic_rpc_handlers((generic_handler,))


# This class is part of an EXPERIMENTAL API.
class Parameter_server(object):
    """Missing associated documentation comment in .proto file."""

    @staticmethod
    def CLIENT_GET(
        request,
        target,
        options=(),
        channel_credentials=None,
        call_credentials=None,
        insecure=False,
        compression=None,
        wait_for_ready=None,
        timeout=None,
        metadata=None,
    ):
        return grpc.experimental.unary_unary(
            request,
            target,
            "/propius_parameter_server.Parameter_server/CLIENT_GET",
            parameter__server__pb2.job.SerializeToString,
            parameter__server__pb2.job.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
        )

    @staticmethod
    def CLIENT_PUSH(
        request,
        target,
        options=(),
        channel_credentials=None,
        call_credentials=None,
        insecure=False,
        compression=None,
        wait_for_ready=None,
        timeout=None,
        metadata=None,
    ):
        return grpc.experimental.unary_unary(
            request,
            target,
            "/propius_parameter_server.Parameter_server/CLIENT_PUSH",
            parameter__server__pb2.job.SerializeToString,
            parameter__server__pb2.ack.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
        )

    @staticmethod
    def JOB_PUT(
        request,
        target,
        options=(),
        channel_credentials=None,
        call_credentials=None,
        insecure=False,
        compression=None,
        wait_for_ready=None,
        timeout=None,
        metadata=None,
    ):
        return grpc.experimental.unary_unary(
            request,
            target,
            "/propius_parameter_server.Parameter_server/JOB_PUT",
            parameter__server__pb2.job.SerializeToString,
            parameter__server__pb2.ack.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
        )

    @staticmethod
    def JOB_GET(
        request,
        target,
        options=(),
        channel_credentials=None,
        call_credentials=None,
        insecure=False,
        compression=None,
        wait_for_ready=None,
        timeout=None,
        metadata=None,
    ):
        return grpc.experimental.unary_unary(
            request,
            target,
            "/propius_parameter_server.Parameter_server/JOB_GET",
            parameter__server__pb2.job.SerializeToString,
            parameter__server__pb2.job.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
        )

    @staticmethod
    def JOB_DELETE(
        request,
        target,
        options=(),
        channel_credentials=None,
        call_credentials=None,
        insecure=False,
        compression=None,
        wait_for_ready=None,
        timeout=None,
        metadata=None,
    ):
        return grpc.experimental.unary_unary(
            request,
            target,
            "/propius_parameter_server.Parameter_server/JOB_DELETE",
            parameter__server__pb2.job.SerializeToString,
            parameter__server__pb2.ack.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
        )
