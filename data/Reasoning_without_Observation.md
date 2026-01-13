---
title: "Reasoning without Observation"
source: "https://langchain-ai.github.io/langgraph/tutorials/rewoo/rewoo/"
content_length: 27654
---

# Reasoning without Observation

**Source:** [https://langchain-ai.github.io/langgraph/tutorials/rewoo/rewoo/](https://langchain-ai.github.io/langgraph/tutorials/rewoo/rewoo/)

## Contenu

[ ](<https://github.com/langchain-ai/langgraph/edit/main/docs/docs/tutorials/rewoo/rewoo.ipynb> "Edit this page")
# Reasoning without Observation¶
In [ReWOO](<https://arxiv.org/abs/2305.18323>), Xu, et. al, propose an agent that combines a multi-step planner and variable substitution for effective tool use. It was designed to improve on the ReACT-style agent architecture in the following ways:
1. Reduce token consumption and execution time by generating the full chain of tools used in a single pass. (_ReACT-style agent architecture requires many LLM calls with redundant prefixes (since the system prompt and previous steps are provided to the LLM for each reasoning step_)
2. Simplify the fine-tuning process. Since the planning data doesn't depend on the outputs of the tool, models can be fine-tuned without actually invoking the tools (in theory).
The following diagram outlines ReWOO's overall computation graph:
ReWOO is made of 3 modules:
1. 🧠
* Planner
* : Generate the plan in the following format:
[code]Plan: <reasoning>
#E1 = Tool[argument for tool]
Plan: <reasoning>
#E2 = Tool[argument for tool with #E1 variable substitution]
```
2.
* Worker
* : executes the tool with the provided arguments.
3. 🧠
* Solver
* : generates the answer for the initial task based on the tool observations.
The modules with a 🧠 emoji depend on an LLM call. Notice that we avoid redundant calls to the planner LLM by using variable substitution.
In this example, each module is represented by a LangGraph node. The end result will leave a trace that looks [like this one](<https://smith.langchain.com/public/39dbdcf8-fbcc-4479-8e28-15377ca5e653/r>). Let's get started!
## Setup¶
For this example, we will provide the agent with a Tavily search engine tool. You can get an API key [here](<https://app.tavily.com/sign-in>) or replace with a free tool option (e.g., [duck duck go search](<https://python.langchain.com/docs/integrations/tools/ddg/>)).
Let's install the required packages and set our API keys
```
pip install -U langgraph langchain_community langchain_openai tavily-python
```
```
import getpass
import os
def _set_if_undefined(var: str):
if not os.environ.get(var):
os.environ[var] = getpass.getpass(f"{var}=")
_set_if_undefined("TAVILY_API_KEY")
_set_if_undefined("OPENAI_API_KEY")
```
Set up [LangSmith](<https://smith.langchain.com>) for LangGraph development
Sign up for LangSmith to quickly spot issues and improve the performance of your LangGraph projects. LangSmith lets you use trace data to debug, test, and monitor your LLM apps built with LangGraph — read more about how to get started [here](<https://docs.smith.langchain.com>).
## Define graph state¶
In LangGraph, every node updates a shared graph state. The state is the input to any node whenever it is invoked.
Below, we will define a state dict to contain the task, plan, steps, and other variables.
```
from typing import List
from typing_extensions import TypedDict
class ReWOO(TypedDict):
task: str
plan_string: str
steps: List
results: dict
result: str
```
## Planner¶
The planner prompts an LLM to generate a plan in the form of a task list. The arguments to each task are strings that may contain special variables (`#E{0-9}+`) that are used for variable substitution from other task results.
Our example agent will have two tools: 1\. Google - a search engine (in this case Tavily) 2\. LLM - an LLM call to reason about previous outputs.
The LLM tool receives less of the prompt context and so can be more token-efficient than the ReACT paradigm.
_API Reference:[ChatOpenAI](<https://python.langchain.com/api_reference/openai/chat_models/langchain_openai.chat_models.base.ChatOpenAI.html>)_
```
from langchain_openai import ChatOpenAI
model = ChatOpenAI(model="gpt-4o")
```
```
prompt = """For the following task, make plans that can solve the problem step by step. For each plan, indicate \
which external tool together with tool input to retrieve evidence. You can store the evidence into a \
variable #E that can be called by later tools. (Plan, #E1, Plan, #E2, Plan, ...)
Tools can be one of the following:
(1) Google[input]: Worker that searches results from Google. Useful when you need to find short
and succinct answers about a specific topic. The input should be a search query.
(2) LLM[input]: A pretrained LLM like yourself. Useful when you need to act with general
world knowledge and common sense. Prioritize it when you are confident in solving the problem
yourself. Input can be any instruction.
For example,
Task: Thomas, Toby, and Rebecca worked a total of 157 hours in one week. Thomas worked x
hours. Toby worked 10 hours less than twice what Thomas worked, and Rebecca worked 8 hours
less than Toby. How many hours did Rebecca work?
Plan: Given Thomas worked x hours, translate the problem into algebraic expressions and solve
with Wolfram Alpha. #E1 = WolframAlpha[Solve x + (2x − 10) + ((2x − 10) − 8) = 157]
Plan: Find out the number of hours Thomas worked. #E2 = LLM[What is x, given #E1]
Plan: Calculate the number of hours Rebecca worked. #E3 = Calculator[(2 ∗ #E2 − 10) − 8]
Begin!
Describe your plans with rich details. Each Plan should be followed by only one #E.
Task: {task}"""
```
```
task = "what is the exact hometown of the 2024 mens australian open winner"
```
```
result = model.invoke(prompt.format(task=task))
```
```
print(result.content)
```
```
Plan: Use Google to search for the 2024 Australian Open winner.
#E1 = Google[2024 Australian Open winner]
Plan: Retrieve the name of the 2024 Australian Open winner from the search results.
#E2 = LLM[What is the name of the 2024 Australian Open winner, given #E1]
Plan: Use Google to search for the hometown of the 2024 Australian Open winner.
#E3 = Google[hometown of 2024 Australian Open winner, given #E2]
Plan: Retrieve the hometown of the 2024 Australian Open winner from the search results.
#E4 = LLM[What is the hometown of the 2024 Australian Open winner, given #E3]
```
#### Planner Node¶
To connect the planner to our graph, we will create a `get_plan` node that accepts the `ReWOO` state and returns with a state update for the `steps` and `plan_string` fields.
_API Reference:[ChatPromptTemplate](<https://python.langchain.com/api_reference/core/prompts/langchain_core.prompts.chat.ChatPromptTemplate.html>)_
```
import re
from langchain_core.prompts import ChatPromptTemplate
# Regex to match expressions of the form E#... = ...[...]
regex_pattern = r"Plan:\s
* (.+)\s
* (#E\d+)\s
* =\s
* (\w+)\s
* \[([^\]]+)\]"
prompt_template = ChatPromptTemplate.from_messages([("user", prompt)])
planner = prompt_template | model
def get_plan(state: ReWOO):
task = state["task"]
result = planner.invoke({"task": task})
# Find all matches in the sample text
matches = re.findall(regex_pattern, result.content)
return {"steps": matches, "plan_string": result.content}
```
## Executor¶
The executor receives the plan and executes the tools in sequence.
Below, instantiate the search engine and define the tool execution node.
_API Reference:[TavilySearchResults](<https://python.langchain.com/api_reference/community/tools/langchain_community.tools.tavily_search.tool.TavilySearchResults.html>)_
```
from langchain_community.tools.tavily_search import TavilySearchResults
search = TavilySearchResults()
```
```
def _get_current_task(state: ReWOO):
if "results" not in state or state["results"] is None:
return 1
if len(state["results"]) == len(state["steps"]):
return None
else:
return len(state["results"]) + 1
def tool_execution(state: ReWOO):
"""Worker node that executes the tools of a given plan."""
_step = _get_current_task(state)
_, step_name, tool, tool_input = state["steps"][_step - 1]
_results = (state["results"] or {}) if "results" in state else {}
for k, v in _results.items():
tool_input = tool_input.replace(k, v)
if tool == "Google":
result = search.invoke(tool_input)
elif tool == "LLM":
result = model.invoke(tool_input)
else:
raise ValueError
_results[step_name] = str(result)
return {"results": _results}
```
## Solver¶
The solver receives the full plan and generates the final response based on the responses of the tool calls from the worker.
```
solve_prompt = """Solve the following task or problem. To solve the problem, we have made step-by-step Plan and \
retrieved corresponding Evidence to each Plan. Use them with caution since long evidence might \
contain irrelevant information.
{plan}
Now solve the question or task according to provided Evidence above. Respond with the answer
directly with no extra words.
Task: {task}
Response:"""
def solve(state: ReWOO):
plan = ""
for _plan, step_name, tool, tool_input in state["steps"]:
_results = (state["results"] or {}) if "results" in state else {}
for k, v in _results.items():
tool_input = tool_input.replace(k, v)
step_name = step_name.replace(k, v)
plan += f"Plan: {_plan}\n{step_name} = {tool}[{tool_input}]"
prompt = solve_prompt.format(plan=plan, task=state["task"])
result = model.invoke(prompt)
return {"result": result.content}
```
## Define Graph¶
Our graph defines the workflow. Each of the planner, tool executor, and solver modules are added as nodes.
```
def _route(state):
_step = _get_current_task(state)
if _step is None:
# We have executed all tasks
return "solve"
else:
# We are still executing tasks, loop back to the "tool" node
return "tool"
```
_API Reference:[END](<https://langchain-ai.github.io/langgraph/reference/constants/#langgraph.constants.END>) | [StateGraph](<https://langchain-ai.github.io/langgraph/reference/graphs/#langgraph.graph.state.StateGraph>) | [START](<https://langchain-ai.github.io/langgraph/reference/constants/#langgraph.constants.START>)_
```
from langgraph.graph import END, StateGraph, START
graph = StateGraph(ReWOO)
graph.add_node("plan", get_plan)
graph.add_node("tool", tool_execution)
graph.add_node("solve", solve)
graph.add_edge("plan", "tool")
graph.add_edge("solve", END)
graph.add_conditional_edges("tool", _route)
graph.add_edge(START, "plan")
app = graph.compile()
```
```
for s in app.stream({"task": task}):
print(s)
print("---")
```
```
{'plan': {'plan_string': "Plan: Use Google to search for the 2024 Men's Australian Open winner. #E1 = Google[2024 Men's Australian Open winner]\nPlan: Once the winner is identified, search for their exact hometown using Google. #E2 = Google[Hometown of 2024 Men's Australian Open winner]", 'steps': [("Use Google to search for the 2024 Men's Australian Open winner. ", '#E1', 'Google', "2024 Men's Australian Open winner"), ('Once the winner is identified, search for their exact hometown using Google. ', '#E2', 'Google', "Hometown of 2024 Men's Australian Open winner")]}}
{'tool': {'results': {'#E1': '[{\'url\': \'https://www.cbssports.com/tennis/news/australian-open-2024-jannik-sinner-aryna-sabalenka-crowned-as-grand-slam-singles-champions-at-melbourne-park/\', \'content\': "Qinwen Zheng, 6-3, 6-2\\nOur Latest Tennis Stories\\nSinner, Sabalenka win Australian Open singles titles\\nSinner makes epic comeback to win Australian Open\\n2024 Australian Open odds, Sinner vs. Medvedev picks\\nSabalenka defeats Zheng to win 2024 Australian Open\\n2024 Australian Open odds, Sabalenka vs. Zheng picks\\n2024 Australian Open odds, Medvedev vs. Zverev picks\\nAustralian Open odds: Djokovic vs. Sinner picks, bets\\nAustralian Open odds: Gauff vs. Sabalenka picks, bets\\nAustralian Open odds: Australian Open 2024: Jannik Sinner, Aryna Sabalenka crowned as Grand Slam singles champions at Melbourne Park\\nSinner and Sabalenka took down Daniil Medvedev and Qinwen Zheng in their respective finals\\nJannik Sinner came back from two sets down to beat Daniil Medvedev 3-6, 3-6, 6-4, 6-4, 6-3 in the Australian Open men\'s singles final, earning him his first ever Grand Slam title. Here is all you need to know about the 2024 Australian Open:\\nHow to watch the 2024 Australian Open\\nMen\'s seeding\\nWomen\'s seeding\\nMen\'s final:\\nNo. 4 Jannik Sinner def. The 22-year-old became the first Italian man to win the Australian Open since 1976, and he is also the youngest player to win at Melbourne Park since Novak Djokovic in 2008.\\n No. 3 Daniil Medvedev, 3-6, 3-6, 6-4, 6-4, 6-3\\nWomen\'s final:\\n"}, {\'url\': \'https://ausopen.com/articles/news/sinner-v-medvedev-how-ao-2024-mens-final-was-decided\', \'content\': "MORE: All the stats from the AO 2024 men’s final\\nDaniil Medvedev could not maintain his scintillating start on Sunday night, while first-time major finalist Jannik Sinner simply grew in strength as the five-set contest progressed.\\nSinner, winner: Italian takes first major at AO 2024\\nNEWS\\nSinner, the morning after: “It\'s great emotions, slowly realising what I\'ve done”\\nNEWS\\n Sinner v Medvedev: How the AO 2024 men\'s final was decided\\nJannik Sinner weathered an early onslaught to reel in Daniil Medvedev, growing in potency to win the Australian Open 2024 final – his first Grand Slam singles title.\\n Early in the second set Medvedev was averaging 77 per cent of first serves in for the match, and towards the end of it this figure had dipped to 65. Medvedev had spent more than 20 hours on court in his previous six rounds, the equivalent of almost two more matches than Sinner (who had spent less than 15 hours on court in advancing to the final).\\n During the shift, Sinner’s forehand was gathering speed, having increased from an average of 122.3 km/h in the first set to 128.7 km/h by the third.\\n"}, {\'url\': \'https://m.youtube.com/watch?v=frRVq6FI_5c\', \'content\': \'Watch the highlights of Jannik Sinner v Daniil Medvedev in the final of the Australian Open 2024.Subscribe to keep up with the latest from the Australian Ope...\'}, {\'url\': \'https://www.cbssports.com/tennis/news/australian-open-2024-jannik-sinner-claims-first-grand-slam-title-in-epic-comeback-win-over-daniil-medvedev/\', \'content\': \'"\\nOur Latest Tennis Stories\\nSinner makes epic comeback to win Australian Open\\nSinner, Sabalenka win Australian Open singles titles\\n2024 Australian Open odds, Sinner vs. Medvedev picks\\nSabalenka defeats Zheng to win 2024 Australian Open\\n2024 Australian Open odds, Sabalenka vs. Zheng picks\\n2024 Australian Open odds, Medvedev vs. Zverev picks\\nAustralian Open odds: Djokovic vs. Sinner picks, bets\\nAustralian Open odds: Gauff vs. Sabalenka picks, bets\\nAustralian Open odds: Zheng vs. Yastremska picks, bets\\nNick Kyrgios reveals he\\\'s contemplating retirement\\n© 2004-2024 CBS Interactive. Jannik Sinner claims first Grand Slam title in epic comeback win over Daniil Medvedev\\nSinner, 22, rallied back from a two-set deficit to become the third ever Italian Grand Slam men\\\'s singles champion\\nAfter almost four hours, Jannik Sinner climbed back from a two-set deficit to win his first ever Grand Slam title with an epic 3-6, 3-6, 6-4, 6-4, 6-3 comeback victory against Daniil Medvedev. Sinner became the first Italian man to win the Australian Open since 1976, and just the eighth man to successfully come back from two sets down in a major final.\\n He did not drop a single set until his meeting with Djokovic, and that win in itself was an accomplishment as Djokovic was riding a 33-match winning streak at the Australian Open and had never lost a semifinal in Melbourne.\\n @janniksin • @wwos • @espn • @eurosport • @wowowtennis pic.twitter.com/DTCIqWoUoR\\n"We are trying to get better everyday, and even during the tournament, trying to get stronger and understand the situation a little bit better," Sinner said.\'}, {\'url\': \'https://m.youtube.com/watch?v=FQxTbCczz-g\', \'content\': \'The moment Jannik Sinner won his first Grand Slam title after beating Daniil Medvedev in the final of the Australian Open 2024.Subscribe to keep up with the ...\'}]'}}}
{'tool': {'results': {'#E1': '[{\'url\': \'https://www.cbssports.com/tennis/news/australian-open-2024-jannik-sinner-aryna-sabalenka-crowned-as-grand-slam-singles-champions-at-melbourne-park/\', \'content\': "Qinwen Zheng, 6-3, 6-2\\nOur Latest Tennis Stories\\nSinner, Sabalenka win Australian Open singles titles\\nSinner makes epic comeback to win Australian Open\\n2024 Australian Open odds, Sinner vs. Medvedev picks\\nSabalenka defeats Zheng to win 2024 Australian Open\\n2024 Australian Open odds, Sabalenka vs. Zheng picks\\n2024 Australian Open odds, Medvedev vs. Zverev picks\\nAustralian Open odds: Djokovic vs. Sinner picks, bets\\nAustralian Open odds: Gauff vs. Sabalenka picks, bets\\nAustralian Open odds: Australian Open 2024: Jannik Sinner, Aryna Sabalenka crowned as Grand Slam singles champions at Melbourne Park\\nSinner and Sabalenka took down Daniil Medvedev and Qinwen Zheng in their respective finals\\nJannik Sinner came back from two sets down to beat Daniil Medvedev 3-6, 3-6, 6-4, 6-4, 6-3 in the Australian Open men\'s singles final, earning him his first ever Grand Slam title. Here is all you need to know about the 2024 Australian Open:\\nHow to watch the 2024 Australian Open\\nMen\'s seeding\\nWomen\'s seeding\\nMen\'s final:\\nNo. 4 Jannik Sinner def. The 22-year-old became the first Italian man to win the Australian Open since 1976, and he is also the youngest player to win at Melbourne Park since Novak Djokovic in 2008.\\n No. 3 Daniil Medvedev, 3-6, 3-6, 6-4, 6-4, 6-3\\nWomen\'s final:\\n"}, {\'url\': \'https://ausopen.com/articles/news/sinner-v-medvedev-how-ao-2024-mens-final-was-decided\', \'content\': "MORE: All the stats from the AO 2024 men’s final\\nDaniil Medvedev could not maintain his scintillating start on Sunday night, while first-time major finalist Jannik Sinner simply grew in strength as the five-set contest progressed.\\nSinner, winner: Italian takes first major at AO 2024\\nNEWS\\nSinner, the morning after: “It\'s great emotions, slowly realising what I\'ve done”\\nNEWS\\n Sinner v Medvedev: How the AO 2024 men\'s final was decided\\nJannik Sinner weathered an early onslaught to reel in Daniil Medvedev, growing in potency to win the Australian Open 2024 final – his first Grand Slam singles title.\\n Early in the second set Medvedev was averaging 77 per cent of first serves in for the match, and towards the end of it this figure had dipped to 65. Medvedev had spent more than 20 hours on court in his previous six rounds, the equivalent of almost two more matches than Sinner (who had spent less than 15 hours on court in advancing to the final).\\n During the shift, Sinner’s forehand was gathering speed, having increased from an average of 122.3 km/h in the first set to 128.7 km/h by the third.\\n"}, {\'url\': \'https://m.youtube.com/watch?v=frRVq6FI_5c\', \'content\': \'Watch the highlights of Jannik Sinner v Daniil Medvedev in the final of the Australian Open 2024.Subscribe to keep up with the latest from the Australian Ope...\'}, {\'url\': \'https://www.cbssports.com/tennis/news/australian-open-2024-jannik-sinner-claims-first-grand-slam-title-in-epic-comeback-win-over-daniil-medvedev/\', \'content\': \'"\\nOur Latest Tennis Stories\\nSinner makes epic comeback to win Australian Open\\nSinner, Sabalenka win Australian Open singles titles\\n2024 Australian Open odds, Sinner vs. Medvedev picks\\nSabalenka defeats Zheng to win 2024 Australian Open\\n2024 Australian Open odds, Sabalenka vs. Zheng picks\\n2024 Australian Open odds, Medvedev vs. Zverev picks\\nAustralian Open odds: Djokovic vs. Sinner picks, bets\\nAustralian Open odds: Gauff vs. Sabalenka picks, bets\\nAustralian Open odds: Zheng vs. Yastremska picks, bets\\nNick Kyrgios reveals he\\\'s contemplating retirement\\n© 2004-2024 CBS Interactive. Jannik Sinner claims first Grand Slam title in epic comeback win over Daniil Medvedev\\nSinner, 22, rallied back from a two-set deficit to become the third ever Italian Grand Slam men\\\'s singles champion\\nAfter almost four hours, Jannik Sinner climbed back from a two-set deficit to win his first ever Grand Slam title with an epic 3-6, 3-6, 6-4, 6-4, 6-3 comeback victory against Daniil Medvedev. Sinner became the first Italian man to win the Australian Open since 1976, and just the eighth man to successfully come back from two sets down in a major final.\\n He did not drop a single set until his meeting with Djokovic, and that win in itself was an accomplishment as Djokovic was riding a 33-match winning streak at the Australian Open and had never lost a semifinal in Melbourne.\\n @janniksin • @wwos • @espn • @eurosport • @wowowtennis pic.twitter.com/DTCIqWoUoR\\n"We are trying to get better everyday, and even during the tournament, trying to get stronger and understand the situation a little bit better," Sinner said.\'}, {\'url\': \'https://m.youtube.com/watch?v=FQxTbCczz-g\', \'content\': \'The moment Jannik Sinner won his first Grand Slam title after beating Daniil Medvedev in the final of the Australian Open 2024.Subscribe to keep up with the ...\'}]', '#E2': '[{\'url\': "https://en.wikipedia.org/wiki/2024_Australian_Open_–_Men\'s_singles_final", \'content\': "This was the first Australian Open final since 2005 not to feature any of the Big Three members.[5]\\nMedvedev set an Open Era record for the most time spent playing at a singles major, at 24 hours and 17 minutes.[6] Medvedev also became the first player in the Open Era to lose two major finals after having a two-set lead.[7]\\nBackground[edit]\\nEntering the final, Medvedev lead the career head-to-head 6–3. He became the second Italian man in the Open Era to win a singles major, after Adriano Panatta at the 1976 French Open,[2] and the first new Australian Open champion in ten years, since Stan Wawrinka in 2014.[3] At 22, Sinner was the youngest Australian Open men\'s singles champion and finalist since Novak Djokovic in 2008.[4] Contents\\n2024 Australian Open – Men\'s singles final\\nThe 2024 Australian Open Men\'s Singles final was the championship tennis match of the men\'s singles tournament at the 2024 Australian Open, contested by fourth-seed Jannik Sinner and third-seed Daniil Medvedev. Also in the semifinals, Medvedev came back from two-sets-to-love down against Alexander Zverev to reach a third Australian Open final.[9] Medvedev had already played two other five-set matches, against Emil Ruusuvuori in the second round (when he came back from two-sets-to-love down as well) and against Hubert Hurkacz in the quarterfinals.\\n Novak Djokovic, ending his 33-match winning streak at the Australian Open (dating back from the 2019 tournament), as well as marking the Serbian\'s first-ever defeat in an Australian Open semifinal and his first defeat in any major semifinal since the 2019 French Open."}, {\'url\': "https://en.wikipedia.org/wiki/2024_Australian_Open_–_Men\'s_singles", \'content\': "Jannik Sinner defeated Daniil Medvedev in the final, 3-6, 3-6, 6-4, 6-4, 6-3 to win the men\'s singles tennis title at the 2024 Australian Open.It was his first major singles title.. Sinner became both the first Italian to win the Australian Open and the second Italian man in the Open Era to win a singles major, after Adriano Panatta at the 1976 French Open. [1]"}, {\'url\': \'https://www.cbssports.com/tennis/news/australian-open-2024-jannik-sinner-aryna-sabalenka-crowned-as-grand-slam-singles-champions-at-melbourne-park/\', \'content\': "Qinwen Zheng, 6-3, 6-2\\nOur Latest Tennis Stories\\nSinner, Sabalenka win Australian Open singles titles\\nSinner makes epic comeback to win Australian Open\\n2024 Australian Open odds, Sinner vs. Medvedev picks\\nSabalenka defeats Zheng to win 2024 Australian Open\\n2024 Australian Open odds, Sabalenka vs. Zheng picks\\n2024 Australian Open odds, Medvedev vs. Zverev picks\\nAustralian Open odds: Djokovic vs. Sinner picks, bets\\nAustralian Open odds: Gauff vs. Sabalenka picks, bets\\nAustralian Open odds: Australian Open 2024: Jannik Sinner, Aryna Sabalenka crowned as Grand Slam singles champions at Melbourne Park\\nSinner and Sabalenka took down Daniil Medvedev and Qinwen Zheng in their respective finals\\nJannik Sinner came back from two sets down to beat Daniil Medvedev 3-6, 3-6, 6-4, 6-4, 6-3 in the Australian Open men\'s singles final, earning him his first ever Grand Slam title. Here is all you need to know about the 2024 Australian Open:\\nHow to watch the 2024 Australian Open\\nMen\'s seeding\\nWomen\'s seeding\\nMen\'s final:\\nNo. 4 Jannik Sinner def. The 22-year-old became the first Italian man to win the Australian Open since 1976, and he is also the youngest player to win at Melbourne Park since Novak Djokovic in 2008.\\n No. 3 Daniil Medvedev, 3-6, 3-6, 6-4, 6-4, 6-3\\nWomen\'s final:\\n"}, {\'url\': \'https://www.nine.com.au/sport/tennis/australian-open-final-2024-live-results-scores-mens-winner-daniil-medvedev-jannik-sinner-womens-doubles-updates-20240129-p5jcbe.html\', \'content\': "Australian Open day 15 schedule AEDT \\ufeffClick here for all live scores, fixtures and results across all courts Watch the 2024 Australian Open live and exclusive on Nine, 9Now and ad-free on Stan Sport. Women\'s doubles\\ufeff final. From 3pm: \\ufeff[11] Jelena Ostapenko (LAT)/Lyudmyla Kichenok (UKR) def by [2] Su-Wei Hsieh (TWN)/Elise Mertens (BEL) 6-1, 7-5. Men\'s singles final\\ufeff"}, {\'url\': \'https://www.bbc.com/sport/tennis/68120937\', \'content\': \'Live scores, results and order of play\\nAlerts: Get tennis news sent to your phone\\nRelated Topics\\nTop Stories\\nFA Cup: Blackburn Rovers v Wrexham - live text commentary\\nRussian skater Valieva given four-year ban for doping\\nLinks to Barcelona are \\\'totally untrue\\\' - Arteta\\nElsewhere on the BBC\\nThe truth behind the fake grooming scandal\\nFeaturing unseen police footage and interviews with the officers at the heart of the case\\nDid their father and uncle kill Nazi war criminals?\\n A real-life murder mystery following three brothers in their quest for the truth\\nWhat was it like to travel on the fastest plane?\\nTake a behind-the-scenes look at the supersonic story of the Concorde\\nToxic love, ruthless ambition and shocking betrayal\\nTell Me Lies follows a passionate college relationship with unimaginable consequences...\\n "\\nMarathon man Medvedev runs out of steam\\nMedvedev is the first player to lose two Grand Slam finals after winning the opening two sets\\nSo many players with the experience of a Grand Slam final have talked about how different the occasion can be, particularly if it is the first time, and potentially overwhelming.\\n Jannik Sinner beats Daniil Medvedev in Melbourne final\\nJannik Sinner is the youngest player to win the Australian Open men\\\'s title since Novak Djokovic in 2008\\nJannik Sinner landed the Grand Slam title he has long promised with an extraordinary fightback to beat Daniil Medvedev in the Australian Open final.\\n "\\nSinner starts 2024 in inspired form\\nSinner won the first Australian Open men\\\'s final since 2005 which did not feature Roger Federer, Rafael Nadal or Novak Djokovic\\nSinner was brought to the forefront of conversation when discussing Grand Slam champions in 2024 following a stunning end to last season.\\n\'}]'}}}
{'solve': {'result': 'San Candido, Italy'}}
```
```
# Print out the final result
print(s["solve"]["result"])
```
```
San Candido, Italy
```
## Conclusion¶
Congratulations on implementing ReWOO! Before you leave, I'll leave you with a couple limitations of the current implementation from the paper:
1. If little context of the environment is available, the planner will be ineffective in its tool use. This can typically be ameliorated through few-shot prompting and/or fine-tuning.
2. The tasks are still executed in sequence, meaning the total execution time is impacted by _every_ tool call, not just the longest-running in a given step.
Back to top

---
*Document traité automatiquement par le système de recherche agentique*
