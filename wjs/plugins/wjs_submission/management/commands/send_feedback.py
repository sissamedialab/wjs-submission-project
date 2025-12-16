import time

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """
    Send simulated feedback messages to a WebSocket group.

    This management command iterates through predefined feedback steps
    and sends each one to the specified WebSocket group with a delay
    between steps. Intended for testing or simulating task progress.

    Attributes:
        help (str): Description of the command.

    """

    help = "Send simulated feedback to the WS group"

    def add_arguments(self, parser):  # noqa: PLR6301
        """
        Add command-line arguments for the management command.

        Args:
            parser (argparse.ArgumentParser): Parser to which arguments are added.

        """
        parser.add_argument("ws_name", type=str, help="Feedback channel name, e.g. abc-1-42")

    def handle(self, *args, **options):  # noqa: PLR6301
        """
        Send the predefined feedback steps to the WebSocket group.

        Args:
            *args: Variable length argument list.
            **options: Command-line options passed to the command.

        Procedure:
            1. Compute the channel group name from the WebSocket name.
            2. Iterate over each step containing a status and status log.
            3. Send each step to the channel group via `group_send`.
            4. Sleep for 2 seconds between steps to simulate processing time.

        """
        ws_name = options["ws_name"]
        group_name = f"group_{ws_name}"
        channel_layer = get_channel_layer()
        steps = [
            {"status": "started", "text": "Started correctly"},
            {"status": "running", "text": "Conversion in progress"},
            {"status": "debug", "text": "Conversion in progress"},
            {"status": "completed", "text": "Conversion completed without errors"},
            {"status": "error", "text": "Conversion completed without errors"},
        ]

        for step in steps:
            async_to_sync(channel_layer.group_send)(
                group_name,
                {"type": "feedback.message", "message": step},
            )
            time.sleep(2)
