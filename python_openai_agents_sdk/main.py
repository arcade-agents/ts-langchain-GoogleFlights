from agents import (Agent, Runner, AgentHooks, Tool, RunContextWrapper,
                    TResponseInputItem,)
from functools import partial
from arcadepy import AsyncArcade
from agents_arcade import get_arcade_tools
from typing import Any
from human_in_the_loop import (UserDeniedToolCall,
                               confirm_tool_usage,
                               auth_tool)

import globals


class CustomAgentHooks(AgentHooks):
    def __init__(self, display_name: str):
        self.event_counter = 0
        self.display_name = display_name

    async def on_start(self,
                       context: RunContextWrapper,
                       agent: Agent) -> None:
        self.event_counter += 1
        print(f"### ({self.display_name}) {
              self.event_counter}: Agent {agent.name} started")

    async def on_end(self,
                     context: RunContextWrapper,
                     agent: Agent,
                     output: Any) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {
                # agent.name} ended with output {output}"
                agent.name} ended"
        )

    async def on_handoff(self,
                         context: RunContextWrapper,
                         agent: Agent,
                         source: Agent) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {
                source.name} handed off to {agent.name}"
        )

    async def on_tool_start(self,
                            context: RunContextWrapper,
                            agent: Agent,
                            tool: Tool) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}:"
            f" Agent {agent.name} started tool {tool.name}"
            f" with context: {context.context}"
        )

    async def on_tool_end(self,
                          context: RunContextWrapper,
                          agent: Agent,
                          tool: Tool,
                          result: str) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {
                # agent.name} ended tool {tool.name} with result {result}"
                agent.name} ended tool {tool.name}"
        )


async def main():

    context = {
        "user_id": os.getenv("ARCADE_USER_ID"),
    }

    client = AsyncArcade()

    arcade_tools = await get_arcade_tools(
        client, toolkits=["GoogleFlights"]
    )

    for tool in arcade_tools:
        # - human in the loop
        if tool.name in ENFORCE_HUMAN_CONFIRMATION:
            tool.on_invoke_tool = partial(
                confirm_tool_usage,
                tool_name=tool.name,
                callback=tool.on_invoke_tool,
            )
        # - auth
        await auth_tool(client, tool.name, user_id=context["user_id"])

    agent = Agent(
        name="",
        instructions="# Introduction
Welcome to the AI Flight Assistant! This agent is designed to help you find the best one-way flights based on your travel preferences. By utilizing Google Flights, the agent can search for flights across various parameters, ensuring you get the most appropriate options for your journey.

# Instructions
1. **Gather User Preferences**: Ask the user for their departure airport code, destination airport code, outbound travel date, and any additional preferences such as currency, travel class, or the number of passengers.
2. **Validate Inputs**: Ensure that the provided airport codes are valid and the date is in the correct format (YYYY-MM-DD).
3. **Search for Flights**: Use the GoogleFlights_SearchOneWayFlights tool with the collected parameters to retrieve flight options.
4. **Present Results**: Display the flight options to the user, including key details such as price, duration, and layovers.
5. **Handle Follow-Up Questions**: Be prepared to respond to user inquiries or additional preferences they may have after viewing the initial results.

# Workflows
1. **Initial Flight Search Workflow**
   - **Step 1**: Gather user inputs: departure airport code, arrival airport code, outbound date, currency (optional), travel class (optional), number of adults (optional), number of children (optional), max stops (optional), and sorting preference (optional).
   - **Step 2**: Validate the inputs.
   - **Step 3**: Execute the GoogleFlights_SearchOneWayFlights tool using the validated inputs.
   - **Step 4**: Present the flight results to the user.

2. **Refinement Workflow**
   - **Step 1**: Ask the user if they'd like to refine their search based on specific criteria such as price range or fewer stops.
   - **Step 2**: Gather the user's new preferences.
   - **Step 3**: Re-execute the GoogleFlights_SearchOneWayFlights tool with the updated preferences.
   - **Step 4**: Present the updated flight options to the user.

3. **Follow-Up Workflow**
   - **Step 1**: Listen for any follow-up questions or requests from the user regarding the flight options.
   - **Step 2**: Provide additional information when necessary, such as tips on booking or answering specific queries about flights.
   - **Step 3**: Ensure user satisfaction and offer to help with any other travel needs.",
        model=os.environ["OPENAI_MODEL"],
        tools=arcade_tools,
        hooks=CustomAgentHooks(display_name="")
    )

    # initialize the conversation
    history: list[TResponseInputItem] = []
    # run the loop!
    while True:
        prompt = input("You: ")
        if prompt.lower() == "exit":
            break
        history.append({"role": "user", "content": prompt})
        try:
            result = await Runner.run(
                starting_agent=agent,
                input=history,
                context=context
            )
            history = result.to_input_list()
            print(result.final_output)
        except UserDeniedToolCall as e:
            history.extend([
                {"role": "assistant",
                 "content": f"Please confirm the call to {e.tool_name}"},
                {"role": "user",
                 "content": "I changed my mind, please don't do it!"},
                {"role": "assistant",
                 "content": f"Sure, I cancelled the call to {e.tool_name}."
                 " What else can I do for you today?"
                 },
            ])
            print(history[-1]["content"])

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())