from arcadepy import AsyncArcade
from dotenv import load_dotenv
from google.adk import Agent, Runner
from google.adk.artifacts import InMemoryArtifactService
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService, Session
from google_adk_arcade.tools import get_arcade_tools
from google.genai import types
from human_in_the_loop import auth_tool, confirm_tool_usage

import os

load_dotenv(override=True)


async def main():
    app_name = "my_agent"
    user_id = os.getenv("ARCADE_USER_ID")

    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    client = AsyncArcade()

    agent_tools = await get_arcade_tools(
        client, toolkits=["GoogleFlights"]
    )

    for tool in agent_tools:
        await auth_tool(client, tool_name=tool.name, user_id=user_id)

    agent = Agent(
        model=LiteLlm(model=f"openai/{os.environ["OPENAI_MODEL"]}"),
        name="google_agent",
        instruction="# Introduction
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
        description="An agent that uses GoogleFlights tools provided to perform any task",
        tools=agent_tools,
        before_tool_callback=[confirm_tool_usage],
    )

    session = await session_service.create_session(
        app_name=app_name, user_id=user_id, state={
            "user_id": user_id,
        }
    )
    runner = Runner(
        app_name=app_name,
        agent=agent,
        artifact_service=artifact_service,
        session_service=session_service,
    )

    async def run_prompt(session: Session, new_message: str):
        content = types.Content(
            role='user', parts=[types.Part.from_text(text=new_message)]
        )
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):
            if event.content.parts and event.content.parts[0].text:
                print(f'** {event.author}: {event.content.parts[0].text}')

    while True:
        user_input = input("User: ")
        if user_input.lower() == "exit":
            print("Goodbye!")
            break
        await run_prompt(session, user_input)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())