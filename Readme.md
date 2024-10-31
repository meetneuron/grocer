# Grocer - Grocery AI Agent

Welcome to Team Neuron's submission for the Databricks 2024 Gen AI Hackathon.

[Demo Video](https://www.youtube.com/watch?v=jWJrtSschmk&ab_channel=neuron)

This "Multi Agent" solution comprises of:
1. Data preperation notebook.
2. ReAct Agent
3. RAG tools on multiple Vector Databases
4. SQL Agents
5. Front end Shiny chatbot

Features/Innovations to note:
1. Auto documentation generation of table & schema using LLM, helping SQL agents.
2. Inventory search based on free text of products, instead of product IDs.
3. Use of Open Source APIs for weather resolution.
   
   Special thanks to [geopy](https://github.com/geopy/geopy) MIT License  and [meteostat](https://github.com/meteostat/meteostat-python). MIT License.
   
   Usage of above while open, please go to their respective webpages to know more.
   
   Geopy with Nominatum is only used here for simple demo purposes to support OpenStreetMap. Read https://operations.osmfoundation.org/policies/nominatim/.

6. Integration with email tool to send mail.
7. Test steps in agent code for unit testing.
8. Focus on easy to use flow for user using prompt engineering. Guardrails to avoid halucination.
9. And many more you see, as you explore code and watch our demo video above.

What next?
1. Implementation of guardrails using LlamaGuard.
2. Modularizing the LangGraph with edges and nodes to bring more control on deterministic behaviour.

![](Slide1.png)
![](Slide2.png)
![](Slide3.png)
