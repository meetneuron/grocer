# Grocer - Grocery AI Agent

This is created for Databricks 2024 Gen AI Hackathon submission by Team Neuron.

This "Multi Agent" solution comprises of:
1. ReAct Agent
2. RAG tools on Multiple Vector Databases
3. SQL Agents
4. Front end chatbot

Respositoty includes Data Preperation notebook.

Features/Innovations to note:
1. Auto documentation generation of table & schema using LLM, helping SQL agents.
2. Inventory search based on free text of products, instead of product ID's.
3. Use of Open Source API's for weather resolution.
   
   Special thanks to [geopy](https://github.com/geopy/geopy) MIT License  and [meteostat](https://github.com/meteostat/meteostat-python). MIT License.
   
   Usage of above while open, please go to their respective webpages to know more.
   
   Geopy with Nominatum need to be used only for simple demo to support OpenStreetMap. Read https://operations.osmfoundation.org/policies/nominatim/ 

6. Integration with email tool to send mail.
7. Test steps in agent code for unit testing.
8. Focus on easy to use flow for user using prompt engineering. Also guardrails to avoid halucination.
9. And many more you see, as you explore code. We will create a seperate video, explaining in depth.

What next?
1. Implementation of guardrails using LlamaGuard.
2. Modularizing the LangGraph with edges and nodes to bring more control on deterministic behaviour.
   

![](Slide1.png)
![](Slide2.png)
![](Slide3.png)
