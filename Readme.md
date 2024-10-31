# Grocer - Grocery AI Agent

Welcome to Team Neuron's submission for the Databricks 2024 Gen AI Hackathon.

[Demo Video](https://www.youtube.com/watch?v=jWJrtSschmk&ab_channel=neuron)

This "Multi Agent" solution comprises of:
 * Data preperation notebook.
 * ReAct Agent
 * RAG tools on multiple Vector Databases
 * SQL Agents
 * Front end Shiny chatbot

Features/Innovations to note:
 * Auto documentation generation of table & schema using LLM, helping SQL agents.
 * Inventory search based on free text of products, instead of product IDs.
 * Use of Open Source APIs for weather resolution.
   
   Special thanks to [geopy](https://github.com/geopy/geopy) MIT License  and [meteostat](https://github.com/meteostat/meteostat-python). MIT License.
   
   Usage of above while open, please go to their respective webpages to know more.
   
   Geopy with Nominatum is only used here for simple demo purposes to support OpenStreetMap. Read https://operations.osmfoundation.org/policies/nominatim/.

 * Integration with email tool to send mail.
 * Test steps in agent code for unit testing.
 * Focus on easy to use flow for user using prompt engineering. Guardrails to avoid halucination.
 * And many more you see, as you explore code and watch our demo video above.

What next?
 * Implementation of guardrails using LlamaGuard.
 * Modularizing the LangGraph with edges and nodes to bring more control on deterministic behaviour.

![](Slide1.png)
![](Slide2.png)
![](Slide3.png)
