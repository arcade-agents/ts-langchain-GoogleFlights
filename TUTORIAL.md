---
title: "Build a GoogleFlights agent with LangChain (TypeScript) and Arcade"
slug: "ts-langchain-GoogleFlights"
framework: "langchain-ts"
language: "typescript"
toolkits: ["GoogleFlights"]
tools: []
difficulty: "beginner"
generated_at: "2026-03-12T01:34:51Z"
source_template: "ts_langchain"
agent_repo: ""
tags:
  - "langchain"
  - "typescript"
  - "googleflights"
---

# Build a GoogleFlights agent with LangChain (TypeScript) and Arcade

In this tutorial you'll build an AI agent using [LangChain](https://js.langchain.com/) with [LangGraph](https://langchain-ai.github.io/langgraphjs/) in TypeScript and [Arcade](https://arcade.dev) that can interact with GoogleFlights tools — with built-in authorization and human-in-the-loop support.

## Prerequisites

- The [Bun](https://bun.com) runtime
- An [Arcade](https://arcade.dev) account and API key
- An OpenAI API key

## Project Setup

First, create a directory for this project, and install all the required dependencies:

````bash
mkdir googleflights-agent && cd googleflights-agent
bun install @arcadeai/arcadejs @langchain/langgraph @langchain/core langchain chalk
````

## Start the agent script

Create a `main.ts` script, and import all the packages and libraries. Imports from 
the `"./tools"` package may give errors in your IDE now, but don't worry about those
for now, you will write that helper package later.

````typescript
"use strict";
import { getTools, confirm, arcade } from "./tools";
import { createAgent } from "langchain";
import {
  Command,
  MemorySaver,
  type Interrupt,
} from "@langchain/langgraph";
import chalk from "chalk";
import * as readline from "node:readline/promises";
````

## Configuration

In `main.ts`, configure your agent's toolkits, system prompt, and model. Notice
how the system prompt tells the agent how to navigate different scenarios and
how to combine tool usage in specific ways. This prompt engineering is important
to build effective agents. In fact, the more agentic your application, the more
relevant the system prompt to truly make the agent useful and effective at
using the tools at its disposal.

````typescript
// configure your own values to customize your agent

// The Arcade User ID identifies who is authorizing each service.
const arcadeUserID = process.env.ARCADE_USER_ID;
if (!arcadeUserID) {
  throw new Error("Missing ARCADE_USER_ID. Add it to your .env file.");
}
// This determines which MCP server is providing the tools, you can customize this to make a Slack agent, or Notion agent, etc.
// all tools from each of these MCP servers will be retrieved from arcade
const toolkits=['GoogleFlights'];
// This determines isolated tools that will be
const isolatedTools=[];
// This determines the maximum number of tool definitions Arcade will return
const toolLimit = 100;
// This prompt defines the behavior of the agent.
const systemPrompt = "# One-Way Flight Search Agent (ReAct) \u2014 Prompt\n\n## Introduction\nYou are a ReAct-style AI agent that helps users find one-way flights using the GoogleFlights_SearchOneWayFlights tool. Your goal is to gather required inputs, validate constraints, call the tool correctly, interpret the returned results, and present clear, actionable summaries or ask follow-ups when necessary.\n\nUse the ReAct pattern for interaction: alternate concise internal \"Thought\" lines with explicit \"Action\" calls to the tool, then record \"Observation\" with the tool output, and produce a clear \"Final Answer\" (or follow-up question) for the user.\n\nDo not expose internal chain-of-thought reasoning. Keep \"Thought\" lines short and functional (planning-level). Use the tool only by issuing an explicit Action block with valid parameters.\n\n## Instructions\n- Required user inputs:\n  - departure_airport_code: 3-letter uppercase IATA (e.g., JFK). If user gives a city name, ask which airport or propose common airports and ask to confirm.\n  - arrival_airport_code: 3-letter uppercase IATA.\n  - outbound_date: YYYY-MM-DD. Validate the format and that the date is sensible (e.g., not long past). Ask for clarification if ambiguous (e.g., \"next Monday\" -\u003e ask for exact date).\n- Optional inputs and defaults:\n  - currency_code: default \u0027USD\u0027 if not provided.\n  - travel_class: default \u0027ECONOMY\u0027 if not provided.\n  - num_adults: default 1 if not provided.\n  - num_children: default 0 if not provided.\n  - max_stops: default is any number of stops; user can provide numeric (0, 1, 2, ...) or \"nonstop\"/\"direct\"/\"any\".\n  - sort_by: default TOP_FLIGHTS. If user requests sorting by price/duration/departure time, map to a best-effort sort_by value (use default if uncertain).\n- Validate inputs before calling the tool. If any required info is missing or invalid, ask a concise clarifying question.\n- Use the tool only after inputs are validated and confirmed.\n- If the tool returns no results, follow a systematic refinement workflow (see Workflows) rather than giving up: suggest relaxing constraints or different dates and re-run calls.\n- Present results as a short ranked list (top 3 by default), including for each option at minimum:\n  - Price and currency\n  - Airline(s)\n  - Departure time \u0026 airport\n  - Arrival time \u0026 airport\n  - Duration\n  - Number of stops and connection airports if available\n  - Any fare conditions or basics (if present in tool output)\n- Ask before attempting to book or open external links. Offer follow-up actions (change dates, change stops, compare airports, multi-date scan).\n- Keep final user messages concise, actionable, and user-focused.\n\n## ReAct Interaction Format\nWhen interacting, follow this structure exactly:\n\nThought: \u003cvery short plan or decision \u2014 do not reveal chain-of-thought\u003e\nAction: GoogleFlights_SearchOneWayFlights\nAction Input:\n```\n{\n  \"departure_airport_code\": \"XXX\",\n  \"arrival_airport_code\": \"YYY\",\n  \"outbound_date\": \"YYYY-MM-DD\",\n  \"currency_code\": \"USD\",\n  \"travel_class\": \"ECONOMY\",\n  \"num_adults\": 1,\n  \"num_children\": 0,\n  \"max_stops\": \"ANY\",\n  \"sort_by\": \"TOP_FLIGHTS\"\n}\n```\nObservation: \u003ctool output \u2014 summarize or quote the raw observation\u003e\nThought: \u003cnext step\u003e\n... (repeat Action/Observation as needed)\nFinal Answer: \u003cconcise result for the user or a clarifying question\u003e\n\nDo not include more than necessary internal reasoning in \"Thought\". Keep \"Final Answer\" in normal user-facing language.\n\n## Workflows\nBelow are standard workflows and the precise sequence of actions (tool calls) to follow in each. For workflows that require multiple calls, aggregate and compare results before finalizing the response.\n\n1) Simple one-way search (single call)\n- Goal: Find best one-way flights for given inputs.\n- Sequence:\n  - Validate inputs (airport codes 3 letters, date format).\n  - Action: GoogleFlights_SearchOneWayFlights with provided params.\n  - Observation: Summarize top N (default 3) results and present to user.\n- Example Action Input:\n```\n{\n  \"departure_airport_code\": \"JFK\",\n  \"arrival_airport_code\": \"LAX\",\n  \"outbound_date\": \"2026-03-15\",\n  \"currency_code\": \"USD\",\n  \"travel_class\": \"ECONOMY\",\n  \"num_adults\": 1,\n  \"num_children\": 0,\n  \"max_stops\": \"0\",\n  \"sort_by\": \"PRICE\"\n}\n```\n\n2) Flexible / multi-date scan (looped calls)\n- Goal: Find the cheapest or best options across multiple possible dates (user-specified range or \u00b1N days).\n- Sequence:\n  - Confirm date range or \u00b1N days and other constraints.\n  - For each candidate date in the range:\n    - Action: GoogleFlights_SearchOneWayFlights (one call per date).\n    - Observation: Save/normalize top result(s) per date.\n  - Aggregate observations: rank by price, duration, or user preference.\n  - Final Answer: present the best dates/options and recommend next step.\n- Notes: Limit number of calls to a reasonable maximum (e.g., \u22647 days) unless user permits more.\n\n3) Multi-origin or multi-destination comparison (parallel calls)\n- Goal: Compare prices from multiple departure airports or to multiple destinations.\n- Sequence:\n  - Confirm list of airports (user-provided or proposed).\n  - For each origin/destination pair:\n    - Action: GoogleFlights_SearchOneWayFlights with same date and constraints.\n    - Observation: collect top results.\n  - Aggregate and present a comparison table or ranked list with cheapest/faster options.\n- Example: Compare flights from EWR, JFK, LGA -\u003e LAX on same date.\n\n4) Constraint relaxation and refinement (iterative)\n- Goal: If initial search fails or results are poor, iteratively relax constraints.\n- Sequence:\n  - Initial Action: GoogleFlights_SearchOneWayFlights with strict user constraints (e.g., nonstop, exact date).\n  - Observation: If no results or too expensive, propose and confirm refinements such as:\n    - Allow 1 stop instead of nonstop\n    - Shift date by \u00b11 day\n    - Change travel_class (if user okay)\n    - Use alternate nearby airports\n  - For each confirmed refinement: Action: GoogleFlights_SearchOneWayFlights with updated params -\u003e Observation.\n  - Final Answer: present best refined options and highlight what changed.\n\n5) Sorting and deep results (when user requests a full sorted list)\n- Goal: Provide more than the top 3, sorted per user preference.\n- Sequence:\n  - Action: GoogleFlights_SearchOneWayFlights with sort_by set (if supported).\n  - Observation: present top N (user-specified) with relevant details.\n- Note: If tool supports server-side sorting, use sort_by; otherwise, retrieve top results and do client-side sorting across multiple calls.\n\n## Error handling and best-practices\n- If user supplies a city name instead of an airport code:\n  - Ask which airport they prefer or offer common airports for that city (ask user to confirm).\n- If airport code or date is invalid:\n  - Ask a concise correction question (e.g., \"Please provide the outbound date in YYYY-MM-DD format.\").\n- If tool returns an error or empty result:\n  - Report the error succinctly, suggest 1\u20132 immediate adjustments, and offer to retry.\n- Rate-limit calls and seek user permission for multi-call workflows (e.g., \u201cI can check 7 dates for you \u2014 is that okay?\u201d).\n- Always respect user preferences (if they insist on nonstop, do not relax without permission).\n\n## Example full ReAct run (simple case)\nThought: Validate inputs and run the search.\nAction: GoogleFlights_SearchOneWayFlights\nAction Input:\n```\n{\n  \"departure_airport_code\": \"SFO\",\n  \"arrival_airport_code\": \"ORD\",\n  \"outbound_date\": \"2026-05-10\",\n  \"currency_code\": \"USD\",\n  \"travel_class\": \"ECONOMY\",\n  \"num_adults\": 1,\n  \"num_children\": 0,\n  \"max_stops\": \"ANY\",\n  \"sort_by\": \"TOP_FLIGHTS\"\n}\n```\nObservation: \u003ctool returns results\u003e\nThought: Summarize top 3 options for the user.\nFinal Answer: Here are the top 3 one-way options from SFO to ORD on 2026-05-10 (prices in USD):\n- Option 1 \u2014 Airline X \u2014 $123 \u2014 Departs 07:00 SFO, Arrives 13:10 ORD \u2014 1 stop \u2014 total 5h10m\n- Option 2 \u2014 Airline Y \u2014 $135 \u2014 Departs 09:20 SFO, Arrives 15:00 ORD \u2014 nonstop \u2014 4h40m\n- Option 3 \u2014 Airline Z \u2014 $140 \u2014 Departs 17:30 SFO, Arrives 23:45 ORD \u2014 1 stop \u2014 6h15m\nWould you like me to (a) book one of these, (b) check nearby dates, or (c) compare other departure airports?\n\n---\n\nUse this prompt as the agent\u0027s operating instructions. Adjust conservative limits (max dates checked, max parallel airports) to meet runtime or cost constraints as needed.";
// This determines which LLM will be used inside the agent
const agentModel = process.env.OPENAI_MODEL;
if (!agentModel) {
  throw new Error("Missing OPENAI_MODEL. Add it to your .env file.");
}
// This allows LangChain to retain the context of the session
const threadID = "1";
````

Set the following environment variables in a `.env` file:

````bash
ARCADE_API_KEY=your-arcade-api-key
ARCADE_USER_ID=your-arcade-user-id
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-5-mini
````

## Implementing the `tools.ts` module

The `tools.ts` module fetches Arcade tool definitions and converts them to LangChain-compatible tools using Arcade's Zod schema conversion:

### Create the file and import the dependencies

Create a `tools.ts` file, and add import the following. These will allow you to build the helper functions needed to convert Arcade tool definitions into a format that LangChain can execute. Here, you also define which tools will require human-in-the-loop confirmation. This is very useful for tools that may have dangerous or undesired side-effects if the LLM hallucinates the values in the parameters. You will implement the helper functions to require human approval in this module.

````typescript
import { Arcade } from "@arcadeai/arcadejs";
import {
  type ToolExecuteFunctionFactoryInput,
  type ZodTool,
  executeZodTool,
  isAuthorizationRequiredError,
  toZod,
} from "@arcadeai/arcadejs/lib/index";
import { type ToolExecuteFunction } from "@arcadeai/arcadejs/lib/zod/types";
import { tool } from "langchain";
import {
  interrupt,
} from "@langchain/langgraph";
import readline from "node:readline/promises";

// This determines which tools require human in the loop approval to run
const TOOLS_WITH_APPROVAL = [];
````

### Create a confirmation helper for human in the loop

The first helper that you will write is the `confirm` function, which asks a yes or no question to the user, and returns `true` if theuser replied with `"yes"` and `false` otherwise.

````typescript
// Prompt user for yes/no confirmation
export async function confirm(question: string, rl?: readline.Interface): Promise<boolean> {
  let shouldClose = false;
  let interface_ = rl;

  if (!interface_) {
      interface_ = readline.createInterface({
          input: process.stdin,
          output: process.stdout,
      });
      shouldClose = true;
  }

  const answer = await interface_.question(`${question} (y/n): `);

  if (shouldClose) {
      interface_.close();
  }

  return ["y", "yes"].includes(answer.trim().toLowerCase());
}
````

Tools that require authorization trigger a LangGraph interrupt, which pauses execution until the user completes authorization in their browser.

### Create the execution helper

This is a wrapper around the `executeZodTool` function. Before you execute the tool, however, there are two logical checks to be made:

1. First, if the tool the agent wants to invoke is included in the `TOOLS_WITH_APPROVAL` variable, human-in-the-loop is enforced by calling `interrupt` and passing the necessary data to call the `confirm` helper. LangChain will surface that `interrupt` to the agentic loop, and you will be required to "resolve" the interrupt later on. For now, you can assume that the reponse of the `interrupt` will have enough information to decide whether to execute the tool or not, depending on the human's reponse.
2. Second, if the tool was approved by the human, but it doesn't have the authorization of the integration to run, then you need to present an URL to the user so they can authorize the OAuth flow for this operation. For this, an execution is attempted, that may fail to run if the user is not authorized. When it fails, you interrupt the flow and send the authorization request for the harness to handle. If the user authorizes the tool, the harness will reply with an `{authorized: true}` object, and the system will retry the tool call without interrupting the flow.

````typescript
export function executeOrInterruptTool({
  zodToolSchema,
  toolDefinition,
  client,
  userId,
}: ToolExecuteFunctionFactoryInput): ToolExecuteFunction<any> {
  const { name: toolName } = zodToolSchema;

  return async (input: unknown) => {
    try {

      // If the tool is on the list that enforces human in the loop, we interrupt the flow and ask the user to authorize the tool

      if (TOOLS_WITH_APPROVAL.includes(toolName)) {
        const hitl_response = interrupt({
          authorization_required: false,
          hitl_required: true,
          tool_name: toolName,
          input: input,
        });

        if (!hitl_response.authorized) {
          // If the user didn't approve the tool call, we throw an error, which will be handled by LangChain
          throw new Error(
            `Human in the loop required for tool call ${toolName}, but user didn't approve.`
          );
        }
      }

      // Try to execute the tool
      const result = await executeZodTool({
        zodToolSchema,
        toolDefinition,
        client,
        userId,
      })(input);
      return result;
    } catch (error) {
      // If the tool requires authorization, we interrupt the flow and ask the user to authorize the tool
      if (error instanceof Error && isAuthorizationRequiredError(error)) {
        const response = await client.tools.authorize({
          tool_name: toolName,
          user_id: userId,
        });

        // We interrupt the flow here, and pass everything the handler needs to get the user's authorization
        const interrupt_response = interrupt({
          authorization_required: true,
          authorization_response: response,
          tool_name: toolName,
          url: response.url ?? "",
        });

        // If the user authorized the tool, we retry the tool call without interrupting the flow
        if (interrupt_response.authorized) {
          const result = await executeZodTool({
            zodToolSchema,
            toolDefinition,
            client,
            userId,
          })(input);
          return result;
        } else {
          // If the user didn't authorize the tool, we throw an error, which will be handled by LangChain
          throw new Error(
            `Authorization required for tool call ${toolName}, but user didn't authorize.`
          );
        }
      }
      throw error;
    }
  };
}
````

### Create the tool retrieval helper

The last helper function of this module is the `getTools` helper. This function will take the configurations you defined in the `main.ts` file, and retrieve all of the configured tool definitions from Arcade. Those definitions will then be converted to LangGraph `Function` tools, and will be returned in a format that LangChain can present to the LLM so it can use the tools and pass the arguments correctly. You will pass the `executeOrInterruptTool` helper you wrote in the previous section so all the bindings to the human-in-the-loop and auth handling are programmed when LancChain invokes a tool.


````typescript
// Initialize the Arcade client
export const arcade = new Arcade();

export type GetToolsProps = {
  arcade: Arcade;
  toolkits?: string[];
  tools?: string[];
  userId: string;
  limit?: number;
}


export async function getTools({
  arcade,
  toolkits = [],
  tools = [],
  userId,
  limit = 100,
}: GetToolsProps) {

  if (toolkits.length === 0 && tools.length === 0) {
      throw new Error("At least one tool or toolkit must be provided");
  }

  // Todo(Mateo): Add pagination support
  const from_toolkits = await Promise.all(toolkits.map(async (tkitName) => {
      const definitions = await arcade.tools.list({
          toolkit: tkitName,
          limit: limit
      });
      return definitions.items;
  }));

  const from_tools = await Promise.all(tools.map(async (toolName) => {
      return await arcade.tools.get(toolName);
  }));

  const all_tools = [...from_toolkits.flat(), ...from_tools];
  const unique_tools = Array.from(
      new Map(all_tools.map(tool => [tool.qualified_name, tool])).values()
  );

  const arcadeTools = toZod({
    tools: unique_tools,
    client: arcade,
    executeFactory: executeOrInterruptTool,
    userId: userId,
  });

  // Convert Arcade tools to LangGraph tools
  const langchainTools = arcadeTools.map(({ name, description, execute, parameters }) =>
    (tool as Function)(execute, {
      name,
      description,
      schema: parameters,
    })
  );

  return langchainTools;
}
````

## Building the Agent

Back on the `main.ts` file, you can now call the helper functions you wrote to build the agent.

### Retrieve the configured tools

Use the `getTools` helper you wrote to retrieve the tools from Arcade in LangChain format:

````typescript
const tools = await getTools({
  arcade,
  toolkits: toolkits,
  tools: isolatedTools,
  userId: arcadeUserID,
  limit: toolLimit,
});
````

### Write an interrupt handler

When LangChain is interrupted, it will emit an event in the stream that you will need to handle and resolve based on the user's behavior. For a human-in-the-loop interrupt, you will call the `confirm` helper you wrote earlier, and indicate to the harness whether the human approved the specific tool call or not. For an auth interrupt, you will present the OAuth URL to the user, and wait for them to finishe the OAuth dance before resolving the interrupt with `{authorized: true}` or `{authorized: false}` if an error occurred:

````typescript
async function handleInterrupt(
  interrupt: Interrupt,
  rl: readline.Interface
): Promise<{ authorized: boolean }> {
  const value = interrupt.value;
  const authorization_required = value.authorization_required;
  const hitl_required = value.hitl_required;
  if (authorization_required) {
    const tool_name = value.tool_name;
    const authorization_response = value.authorization_response;
    console.log("⚙️: Authorization required for tool call", tool_name);
    console.log(
      "⚙️: Please authorize in your browser",
      authorization_response.url
    );
    console.log("⚙️: Waiting for you to complete authorization...");
    try {
      await arcade.auth.waitForCompletion(authorization_response.id);
      console.log("⚙️: Authorization granted. Resuming execution...");
      return { authorized: true };
    } catch (error) {
      console.error("⚙️: Error waiting for authorization to complete:", error);
      return { authorized: false };
    }
  } else if (hitl_required) {
    console.log("⚙️: Human in the loop required for tool call", value.tool_name);
    console.log("⚙️: Please approve the tool call", value.input);
    const approved = await confirm("Do you approve this tool call?", rl);
    return { authorized: approved };
  }
  return { authorized: false };
}
````

### Create an Agent instance

Here you create the agent using the `createAgent` function. You pass the system prompt, the model, the tools, and the checkpointer. When the agent runs, it will automatically use the helper function you wrote earlier to handle tool calls and authorization requests.

````typescript
const agent = createAgent({
  systemPrompt: systemPrompt,
  model: agentModel,
  tools: tools,
  checkpointer: new MemorySaver(),
});
````

### Write the invoke helper

This last helper function handles the streaming of the agent’s response, and captures the interrupts. When the system detects an interrupt, it adds the interrupt to the `interrupts` array, and the flow interrupts. If there are no interrupts, it will just stream the agent’s to your console.

````typescript
async function streamAgent(
  agent: any,
  input: any,
  config: any
): Promise<Interrupt[]> {
  const stream = await agent.stream(input, {
    ...config,
    streamMode: "updates",
  });
  const interrupts: Interrupt[] = [];

  for await (const chunk of stream) {
    if (chunk.__interrupt__) {
      interrupts.push(...(chunk.__interrupt__ as Interrupt[]));
      continue;
    }
    for (const update of Object.values(chunk)) {
      for (const msg of (update as any)?.messages ?? []) {
        console.log("🤖: ", msg.toFormattedString());
      }
    }
  }

  return interrupts;
}
````

### Write the main function

Finally, write the main function that will call the agent and handle the user input.

Here the `config` object configures the `thread_id`, which tells the agent to store the state of the conversation into that specific thread. Like any typical agent loop, you:

1. Capture the user input
2. Stream the agent's response
3. Handle any authorization interrupts
4. Resume the agent after authorization
5. Handle any errors
6. Exit the loop if the user wants to quit

````typescript
async function main() {
  const config = { configurable: { thread_id: threadID } };
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  console.log(chalk.green("Welcome to the chatbot! Type 'exit' to quit."));
  while (true) {
    const input = await rl.question("> ");
    if (input.toLowerCase() === "exit") {
      break;
    }
    rl.pause();

    try {
      let agentInput: any = {
        messages: [{ role: "user", content: input }],
      };

      // Loop until no more interrupts
      while (true) {
        const interrupts = await streamAgent(agent, agentInput, config);

        if (interrupts.length === 0) {
          break; // No more interrupts, we're done
        }

        // Handle all interrupts
        const decisions: any[] = [];
        for (const interrupt of interrupts) {
          decisions.push(await handleInterrupt(interrupt, rl));
        }

        // Resume with decisions, then loop to check for more interrupts
        // Pass single decision directly, or array for multiple interrupts
        agentInput = new Command({ resume: decisions.length === 1 ? decisions[0] : decisions });
      }
    } catch (error) {
      console.error(error);
    }

    rl.resume();
  }
  console.log(chalk.red("👋 Bye..."));
  process.exit(0);
}

// Run the main function
main().catch((err) => console.error(err));
````

## Running the Agent

### Run the agent

```bash
bun run main.ts
```

You should see the agent responding to your prompts like any model, as well as handling any tool calls and authorization requests.

## Next Steps

- Clone the [repository](https://github.com/arcade-agents/ts-langchain-GoogleFlights) and run it
- Add more toolkits to the `toolkits` array to expand capabilities
- Customize the `systemPrompt` to specialize the agent's behavior
- Explore the [Arcade documentation](https://docs.arcade.dev) for available toolkits

