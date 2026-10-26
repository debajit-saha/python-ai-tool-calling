
import json
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

from helpdesk_functions import run_local_function

PROJECT_ENDPOINT = (
    "https://foundry-dev-eus-902.services.ai.azure.com/"
    "api/projects/proj-default"
)

AGENT_NAME = "IT-HelpDesk-Agent"
AGENT_VERSION = "1"  # Change to the version created by your setup script.
MAX_TOOL_ROUNDS = 5

project = AIProjectClient(
    endpoint=PROJECT_ENDPOINT,
    credential=DefaultAzureCredential(),
)
client = project.get_openai_client()


def run_agent(question: str) -> str:
    conversation = client.conversations.create()

    try:
        response = client.responses.create(
            conversation=conversation.id,
            input=question,
            extra_body={
                "agent_reference": {
                    "type": "agent_reference",
                    "name": AGENT_NAME,
                    "version": AGENT_VERSION,
                }
            },
        )

        for _ in range(MAX_TOOL_ROUNDS):
            tool_outputs = []

            for item in response.output:
                if item.type != "function_call":
                    continue

                function_name = item.name

                try:
                    arguments = json.loads(item.arguments)

                    print(f"Tool requested: {function_name}")
                    print(f"Arguments: {arguments}")

                    result = run_local_function(
                        function_name,
                        arguments,
                    )

                    tool_outputs.append({
                        "type": "function_call_output",
                        "call_id": item.call_id,
                        "output": str(result),
                    })

                except (ValueError, TypeError, KeyError) as exc:
                    tool_outputs.append({
                        "type": "function_call_output",
                        "call_id": item.call_id,
                        "output": json.dumps({
                            "error": "Invalid tool arguments or input",
                        }),
                    })

            # No function calls means the agent has finished.
            if not tool_outputs:
                return response.output_text

            # Return tool results so the agent can continue.
            response = client.responses.create(
                conversation=conversation.id,
                input=tool_outputs,
                extra_body={
                    "agent_reference": {
                        "type": "agent_reference",
                        "name": AGENT_NAME,
                        "version": AGENT_VERSION,
                    }
                },
            )

        return (
            "Stopped after reaching the maximum number "
            "of tool rounds. Please try a simpler request."
        )

    finally:
        client.conversations.delete(
            conversation_id=conversation.id
        )


if __name__ == "__main__":
    question = "My VPN keeps disconnecting, and I also need to install VS Code on my laptop." \
        " Please give me the VPN troubleshooting steps and the VS Code installation guide." \
        " Also, tell me today's date."
    print("\nAgent answer:")
    print(run_agent(question))
