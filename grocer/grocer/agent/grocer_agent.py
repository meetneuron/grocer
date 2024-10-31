# Databricks notebook source
# MAGIC %md
# MAGIC #Agent notebook

# COMMAND ----------

# MAGIC %pip install -U -qqqq mlflow-skinny langchain==0.2.16 langgraph-checkpoint==1.0.12 langchain_core langchain-community==0.2.16 langgraph==0.2.16 pydantic databricks-sql-connector databricks-vectorsearch geopy meteostat 
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Import and setup

# COMMAND ----------

import mlflow

#Vector Search Client
from databricks.vector_search.client import VectorSearchClient

from langchain.tools import StructuredTool
from mlflow.models import ModelConfig

# COMMAND ----------


#For debug in traces.
# mlflow.set_experiment(experiment_id="527359e5b4784ed5a80f36c10fdeffc0")

mlflow.langchain.autolog()




# COMMAND ----------

# MAGIC %md
# MAGIC # Tools

# COMMAND ----------

config = ModelConfig(development_config="config.yml")

# COMMAND ----------

import os
os.environ["DATABRICKS_HOST"]= config.get("DATABRICKS_HOST") 
os.environ["DATABRICKS_TOKEN"]= config.get("DATABRICKS_TOKEN")
os.environ["WORKSPACE_URL"]= config.get("WORKSPACE_URL")

# COMMAND ----------


from langchain_community.chat_models import ChatDatabricks
# Create the llm

llm = ChatDatabricks(endpoint=config.get("llm_endpoint"),temperature=0)

# COMMAND ----------

# llm.invoke("You are a helpful ")

# COMMAND ----------

# help(ChatDatabricks)

# COMMAND ----------

from langchain_community.tools.databricks import UCFunctionToolkit

uc_functions = config.get("uc_functions")

uc_function_tools = (
    UCFunctionToolkit(warehouse_id=config.get("warehouse_id"))
    .include(*uc_functions)
    .get_tools()
)



# COMMAND ----------

# MAGIC %md
# MAGIC ### Database Search Tool

# COMMAND ----------

def search_database(query_str: str) -> str:
    from langchain.agents import create_sql_agent
    from langchain.agents.agent_toolkits import SQLDatabaseToolkit
    from langchain.sql_database import SQLDatabase

    db = SQLDatabase.from_databricks(catalog="genai", schema="data",host=config.get("DATABRICKS_HOST"),
                                         warehouse_id=config.get("warehouse_id"))
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    agent = create_sql_agent(llm=llm, toolkit=toolkit, verbose=True,top_k=100000)

    response=agent.run(query_str)
    return response
# #Try the function here
# search_database("Do we have Apples in Store? What is the price?")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Inventory Tool

# COMMAND ----------

def get_availabiility_price():
    
    def get_product_availability_and_price(products_user_store_details: str)-> str:

        def get_product_details(product_details: str,store_id: str) -> str:
            import os
            workspace_url = os.environ.get("WORKSPACE_URL")


            client = VectorSearchClient(
            workspace_url=workspace_url,disable_notice=True)

            index = client.get_index(endpoint_name='product_vs_endpoint', index_name="genai.llm.product_vsindex")
            results = index.similarity_search( query_text=product_details,
                    columns=["ProductID", "UnitPrice","StoreID","ProductName"],
                    num_results=1,
                    filters={"StoreID": store_id}
                    )
            content=results#['result']['data_array'][0][1]    
            return content

        try:
            message=products_user_store_details

            product_list_prompt=f"""You will only output list of products from the message. You will not generate any other text. You will not output anything other than a list. You will not generate any product name which is not recieved by you. Here is the message: {message}. Example of output is: ['grapes','juice']."""
            product_list_response=llm.invoke(product_list_prompt)
            product_list_content=product_list_response.content
            import ast
            product_list=ast.literal_eval(product_list_content)

            store_list_prompt=f"""You will only output list of store id from the message. You will not generate any other text. You will not output anything other than a list. You will not generate any product name which is not recieved by you. Here is the message: {message}. Example of output is: ['1','2']."""
            store_list_response=llm.invoke(store_list_prompt)
            store_list_content=store_list_response.content
            import ast
            store_list=ast.literal_eval(store_list_content)

            # print (product_list,store_list)

            results=[]
            for store in store_list:
                for product in product_list:
                    result=get_product_details(product,store)
                    row_count=result['result']['row_count']
                    if row_count>0:
                        score=result['result']['data_array'][0][-1]
                        found_product_name=result['result']['data_array'][0][-2]
                        found_product_id=result['result']['data_array'][0][0]
                        found_product_price=result['result']['data_array'][0][1]
                        results.append(
                            {"store":store,
                             "product":product,
                             "found_product_name":found_product_name,
                             "found_product_id":found_product_id,
                             "found_product_price":found_product_price,
                             "product_id":found_product_id,
                             "similiarity_score":score})
                    else:
                        results.append({"store":store,"product":product,"found_product_name":"No Same or similiar product found","found_product_id":f"""No product found for {store}""","similiarity_score":0})

            # print (results)

            inventory_check_info=str(results)

            prompt=f"""You will do comparision between product name and found product name recieved. Your decisons are not impacted by similiarity scores. Then you will decide if we can conclusively say that product is available or not. Provide only summarized inventory check in a single sentence, store wise. You will use the product field to mention if a product is available or not. You will only mention the found product name, found product id and found product price as recieved by you only against products you concluded as available. You will not generate any non factual details which is not in the input to you. {inventory_check_info}"""
            response=llm.invoke(prompt)
            inventory_analysis=response.content
        except Exception as e:
            inventory_analysis=f"""Unable to check inventory. Following error: {e}"""
        return inventory_analysis
    
    get_product_availability_and_price_tool = StructuredTool.from_function(func=get_product_availability_and_price,
                                              name='get_product_availability_and_price',
                                              description='Use this tool to check for the product availability and product price, given list of Product Names and List of User Store ID. Never pass User ID. It will return its analysis.')

    return get_product_availability_and_price_tool

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC ## User Tool

# COMMAND ----------

def get_user_info():
    """
    Input to this tool is user Loyalty ID and related question This tool will help you get details from user data.
    :return: results fetched from data.
    """
    def get_user_details(user_question_with_loyalty_id: str) -> str:

        from langchain.agents import create_sql_agent
        from langchain.agents.agent_toolkits import SQLDatabaseToolkit
        from langchain.sql_database import SQLDatabase

        db = SQLDatabase.from_databricks(catalog="genai", schema="data",host=config.get("DATABRICKS_HOST"),
                                         warehouse_id=config.get("warehouse_id"),include_tables=["users"])
        toolkit = SQLDatabaseToolkit(db=db, llm=llm)
        agent = create_sql_agent(llm=llm, toolkit=toolkit, verbose=True,top_k=100000,
                                 agent_executor_kwargs={"handle_parsing_errors": True}
                                 )

        response=agent.run(user_question_with_loyalty_id)
        
        
        return response

    get_user_details_tool = StructuredTool.from_function(func=get_user_details,
                                              name='get_user_details',
                                              description='Input to this tool is user Loyalty ID and related question. This tool will help you get details from user data.')

    return get_user_details_tool

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC ## Offer Tool

# COMMAND ----------

def get_offers():
    """
    Get offered products and offered points for user if user purchases the offered products.
    :return: results fetched from data.
    """
    def get_offers_details(user_input: str) -> str:

        from langchain.agents import create_sql_agent
        from langchain.agents.agent_toolkits import SQLDatabaseToolkit
        from langchain.sql_database import SQLDatabase

        db = SQLDatabase.from_databricks(catalog="genai", schema="data",host=config.get("DATABRICKS_HOST"),
                                         warehouse_id=config.get("warehouse_id"),include_tables=["offers","products"])
        toolkit = SQLDatabaseToolkit(db=db, llm=llm)
        agent = create_sql_agent(llm=llm, toolkit=toolkit, verbose=True,top_k=100000,
                                 agent_executor_kwargs={"handle_parsing_errors": True})

        response=agent.run(user_input)
        
        
        return response

    get_offers_details_tool = StructuredTool.from_function(func=get_offers_details,
                                              name='get_offers_details',
                                              description='Use this tool to get every details of offers from offer table by passing user Loyalty ID.')

    return get_offers_details_tool

# COMMAND ----------

# MAGIC %md
# MAGIC ## Festival Tool

# COMMAND ----------

def get_festivals():
    """
    This tool will take in user location details. Post that based on the festivals within a week of current date it will return list recipies and products.
    :return: results fetched from data.
    """
    def suggest_for_upcoming_festivals(user_details: str) -> str:

        from datetime import datetime
        today=datetime.today().strftime('%Y-%b-%d')
        prompt=f"""Based on user details and current date information you have, you will provide the festival which will be coming soon within couple of weeks from current date. You will provide list of 3 festival names (don't give details of festival) and one famous recipie, and ingredients prepared for each of festivals based on your knowledge. Don't give cooking instructions. Don't give date on when will be the festivals. Mention that these are AI generated, not from database in disclaimer. User Details: {user_details}. Current date: {today}."""
        response=llm.invoke(prompt)
        
        
        return response

    suggest_for_festivals_tool = StructuredTool.from_function(func=suggest_for_upcoming_festivals,
                                              name='suggest_for_upcoming_festivals',
                                              description='This tool will take in user location and other details. Post that based on the festivals around current date it will return list recipies and products.')

    return suggest_for_festivals_tool
    


# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC ## Best before product tool

# COMMAND ----------

def get_expired_products():
    """
    This tool will be used to to get results from transaction data which has all the purchase history of user.
    :return: results fetched from data.
    """
    def get_expired_products_details(product_id_and_loyalty_id_details: str) -> str:

        from langchain.agents import create_sql_agent
        from langchain.agents.agent_toolkits import SQLDatabaseToolkit
        from langchain.sql_database import SQLDatabase

        db = SQLDatabase.from_databricks(catalog="genai", schema="data",host=config.get("DATABRICKS_HOST"),
                                         warehouse_id=config.get("warehouse_id"),include_tables=["transactions"])
        toolkit = SQLDatabaseToolkit(db=db, llm=llm)
        agent = create_sql_agent(llm=llm, toolkit=toolkit, verbose=True,top_k=100000,
                                 agent_executor_kwargs={"handle_parsing_errors": True})

        response=agent.run(product_id_and_loyalty_id_details)
        
        
        return response

    get_expired_products_details_tool = StructuredTool.from_function(func=get_expired_products_details,
                                              name='get_expired_products_details',
                                              description='This tool can be used to to get expired products details by looking in to Product Expiry Date in transactions table. Input to this tool will be Loyalty ID of user.')

    return get_expired_products_details_tool

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC ## Search all schema tool.
# MAGIC Optional tool. Not used as it is highly inconsistent and not optimal to use this.

# COMMAND ----------

def search_in_all_data():
    """
    Input to this tool is user input. This tool is used only if agent wants to search entire database to get relevant answer, will help you get answers for user questions from backend stored data.
    :return: results fetched from data.
    """
    def search_in_all_grocery_data(user_input: str) -> str:

        from langchain.agents import create_sql_agent
        from langchain.agents.agent_toolkits import SQLDatabaseToolkit
        from langchain.sql_database import SQLDatabase

        db = SQLDatabase.from_databricks(catalog="genai", schema="data",host=config.get("DATABRICKS_HOST"),
                                         warehouse_id=config.get("warehouse_id"))
        toolkit = SQLDatabaseToolkit(db=db, llm=llm)
        agent = create_sql_agent(llm=llm, toolkit=toolkit, verbose=True)

        response=agent.run(user_input)
        
        
        return response

    search_in_all_data_tool = StructuredTool.from_function(func=search_in_all_grocery_data,
                                              name='search_in_all_grocery_data',
                                              description='Input to this tool is user question. This tool will help you get answers for user questions from backend stored data.')

    return search_in_all_data_tool

# COMMAND ----------

# MAGIC %md
# MAGIC ## Recipie Tool Vector Search Database

# COMMAND ----------

def get_recipie():
    """
    This function will help you find the recipie.
    :return: the recipie
    """
    def get_stored_recipie(user_input: str) -> str:
        
        import os
        workspace_url = os.environ.get("WORKSPACE_URL")


        client = VectorSearchClient(
            workspace_url=workspace_url,disable_notice=True)

        index = client.get_index(endpoint_name='recipie_vs_endpoint', index_name="genai.llm.recipie_vsindex")
        results = index.similarity_search(
            query_text=user_input,
            columns=["RecipieID", "content"],
            num_results=1
            )
        content=results['result']['data_array'][0][1]
        
        return content

    recipie_tool = StructuredTool.from_function(func=get_stored_recipie,
                                              name='get_stored_recipie',
                                              description='This tool will help you to search for recipie for user input.')

    return recipie_tool

# COMMAND ----------

# MAGIC %md
# MAGIC ## Weather Forecast Tool

# COMMAND ----------


def get_weather():
    """
    This function  will get the weather forecast so that agent can suggest the grocery suited for this weather.
    :return: the weather forecast indicating the weather condition.
    """

    def get_weather_forecast(address: str) -> str:
        
        import datetime
        from datetime import datetime, timedelta
        try:
            #This uses open source metostat and openmap API to get the weather
            city_country=address.split(',')[-2:]
            city_country=','.join(city_country)
            from geopy.geocoders import Nominatim
            from meteostat import Point, Daily
            geolocator = Nominatim(user_agent="test")
            location = geolocator.geocode(city_country)


            #Approximate the forecast to last year one week weather at the same time.
            today = datetime.today()
            start=today+ timedelta(days=-365)
            end=start+ timedelta(days=7)
        
            point = Point(location.latitude, location.longitude, 70)
            data = Daily(point, start, end)
            data = data.fetch()
            temperature=data['tavg'].mean()
            temperature=int(temperature)
            
            if temperature >= 28:
                weather_indicator = "Hot"
            elif 22 <= temperature <= 27:
                weather_indicator = "Warm"
            elif 18 <= temperature <= 21:
                weather_indicator = "Mild"
            elif 12 <= temperature <= 17:
                weather_indicator = "Cool"
            elif 6 <= temperature <= 11:
                weather_indicator = "Cold"
            elif temperature < 0:
                weather_indicator = "Freezing"
            else:
                weather_indicator = "Very Cold"

        except:
            #If above API call fails, a generic fail proof based on month. Not without factual error though.

            from datetime import datetime, timedelta
            current_month = datetime.today().strftime('%Y-%b-%d')
            weather_prompt=f"""You are a weather. You are provided with user address and current month. Based on your knowledge on weather, in a single word you will mention if weather is Hot,Warm,Mild,Cold,Freezing or Very Cold. If you are not able to determine user location from given detail, say "Not able to determine the weather". You will not output other sentnce or word.User Details are: {address}. Current date is {current_month}"""
            weather_indicator=llm.invoke(weather_prompt)
            weather_indicator=weather_indicator.content

        return weather_indicator


    get_weather_forecast_tool = StructuredTool.from_function(func=get_weather_forecast,
                                              name='get_weather_forecast',
                                              description="""This tool will get the weather forecast, for provided user address details so that agent can suggest the grocery suited for user weather.""")

    return get_weather_forecast_tool

# COMMAND ----------

# MAGIC %md
# MAGIC ## Send Email

# COMMAND ----------

def send_email():
    #Extremely dangerous function. use cautiosly in chatbot.

    def send_email_function(user_details_and_conversation_summary: str) -> str:

        prompt=f""" You will return only html code like below. You will not return any text other than HTML code. You will greet the user in the message at the begining. You will extract the grocery list and will place it in a table, by categorizing each product in the list. You will place rest of the information is different tables. Don't mention anything about next steps. You will then create a personalized HTML page. Here is the input details: {user_details_and_conversation_summary}..
        Example of HTML output expected is below:
        <!DOCTYPE html>
            <html>
            <head>
                <link rel="stylesheet" type="text/css" hs-webfonts="true" href="https://fonts.googleapis.com/css?family=Lato|Lato:i,b,bi">
                <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style type="text/css">
                h1{{font-size:56px}}
                h2{{font-size:28px;font-weight:900}}
                p{{font-weight:100}}
                td{{vertical-align:top}}
                #email{{margin:auto;width:600px;background-color:#fff}}
                </style>
            </head>
            <body bgcolor="#F5F8FA" style="width: 100%; font-family:Lato, sans-serif; font-size:18px;">
            <div id="email">
                <table role="presentation" width="100%">
                    <tr>
                        <td bgcolor="#00A4BD" align="center" style="color: white;">
                            <h1> Your Grocery List</h1>
                        </td>
                </table>
                <table role="presentation" border="0" cellpadding="0" cellspacing="10px" style="padding: 30px 30px 30px 60px;">
                    <tr>
                        <td>
                            <h2>Grocery List</h2>
                            <p>
                                {user_details_and_conversation_summary}
                            </p>
                        </td>
                    </tr>
                </table>
            </div>
            </body>
            </html>
        """

        response=llm.invoke(prompt)

        prompt=f""" You will only return the email id in dictionary like below. You will not return any text other than dictionary. You will look for user email ID in recieved content and extract user email id. You will return a dictionary like following. You will never generate email, if not found in the content recieved. You will return 'no email found' in the place of email key value, if there is no email found in recieved content. {{"email":"user@example.com"}} Here is the recieved content: {user_details_and_conversation_summary}"""

        email_extractor=llm.invoke(prompt)

        import ast
        user_email=ast.literal_eval(email_extractor.content)['email']
        receiver_email_id=user_email


        import smtplib
        from email.message import EmailMessage
        from mlflow.models import ModelConfig
        
        config = ModelConfig(development_config="config.yml")

        sender_email_id=config.get("sender_email_id") 
        sender_email_id_password=config.get("sender_email_id_password")
        
        

        if 'no email' in receiver_email_id:
            return_value="Message sending failed as there was no email ID found for user"
        else:
            #Overwriting reciever email ID for demo.
            receiver_email_id=sender_email_id
            msg = EmailMessage()
            msg['Subject'] = 'Grocery List'
            msg['From'] = sender_email_id
            msg['To'] = receiver_email_id
            html_message=response.content
            msg.set_content(html_message, subtype='html')

            # #Use this with caution. Do all security test.
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(sender_email_id, sender_email_id_password)
                smtp.send_message(msg)
            return_value=f"""Message sent to: {receiver_email_id}"""
        return return_value

        
    
    send_mail_tool = StructuredTool.from_function(func=send_email_function,
                                              name='send_email_function',
                                              description="""This tool takes user email details and chatbot conversation summary as recieved by the agent to send email to user.""")

    return send_mail_tool



# COMMAND ----------

# MAGIC %md
# MAGIC # Output parsers
# MAGIC
# MAGIC As provided by databricks out of the box. Commented out tool calls for user experience.

# COMMAND ----------

from typing import Iterator, Dict, Any
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    ToolMessage,
    MessageLikeRepresentation,
)

import json

uc_functions_set = {x.replace(".", "__") for x in uc_functions}


def is_uc_function(tool_name: str) -> bool:
    """Check if `tool_name` is in `uc_functions` or belongs to a schema from config.yml."""
    if tool_name in uc_functions_set:
        return True
    for pattern in uc_functions_set:
        if "*" in pattern and tool_name.startswith(pattern[:-1]):
            return True
    return False


def stringify_tool_call(tool_call: Dict[str, Any]) -> str:
    """Convert a raw tool call into a formatted string that the playground UI expects"""
    if is_uc_function(tool_call.get("name")):
        request = json.dumps(
            {
                "id": tool_call.get("id"),
                "name": tool_call.get("name"),
                "arguments": json.dumps(tool_call.get("args", {})),
            },
            indent=2,
        )
        return f"<uc_function_call>{request}</uc_function_call>"
    else:
        # for non UC functions, return the string representation of tool calls
        # you can modify this to return a different format
        return str(tool_call)


def stringify_tool_result(tool_msg: ToolMessage) -> str:
    """Convert a ToolMessage into a formatted string that the playground UI expects"""
    if is_uc_function(tool_msg.name):
        result = json.dumps(
            {"id": tool_msg.tool_call_id, "content": tool_msg.content}, indent=2
        )
        return f"<uc_function_result>{result}</uc_function_result>"
    else:
        # for non UC functions, return the string representation of tool message
        # you can modify this to return a different format
        return str(tool_msg)


def parse_message(msg) -> str:
    """Parse different message types into their string representations"""
    # tool call result
    if isinstance(msg, ToolMessage):
        return " " #stringify_tool_result(msg)
    # tool call
    elif isinstance(msg, AIMessage) and msg.tool_calls:
        tool_call_results = [stringify_tool_call(call) for call in msg.tool_calls]
        return " " # "".join(tool_call_results)
    # normal HumanMessage or AIMessage (reasoning or final answer)
    elif isinstance(msg, (AIMessage, HumanMessage)):
        return msg.content
    else:
        print(f"Unexpected message type: {type(msg)}")
        return str(msg)


def wrap_output(stream: Iterator[MessageLikeRepresentation]) -> Iterator[str]:
    """
    Process and yield formatted outputs from the message stream.
    The invoke and stream langchain functions produce different output formats.
    This function handles both cases.
    """
    for event in stream:
        # the agent was called with invoke()
        if "messages" in event:
            for msg in event["messages"]:
                yield parse_message(msg) + "\n\n"
        # the agent was called with stream()
        else:
            for node in event:
                for key, messages in event[node].items():
                    if isinstance(messages, list):
                        for msg in messages:
                            yield parse_message(msg) + "\n\n"
                    else:
                        print("Unexpected value {messages} for key {key}. Expected a list of `MessageLikeRepresentation`'s")
                        yield str(messages)

# COMMAND ----------

# MAGIC %md
# MAGIC # React Agent

# COMMAND ----------

all_tools = [
            # search_in_all_data(), #Deprecated. Doesn't provide consistent results for complex query. Cal halucinate a lot.
            # get_product_prices(), #Replaced with single vector search to product table.
            #  get_product_info(), #Replaced with single vector search to product table.
             # get_inventory(), #Replaced with single vector search to product table.
            get_user_info(),
            get_offers(),
            get_availabiility_price(),
            get_expired_products(),
            get_recipie(),
            get_weather(),
            get_festivals(),
            send_email()
             ]
all_tools.extend(uc_function_tools)

# COMMAND ----------

from langchain_core.runnables import RunnableGenerator


config = ModelConfig(development_config="config.yml")

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

try:
    system_message = config.get("agent_prompt")
    agent_with_raw_output = create_react_agent(llm, all_tools, state_modifier=system_message)
except KeyError:
    agent_with_raw_output = create_react_agent(llm, all_tools)

agent = agent_with_raw_output | RunnableGenerator(wrap_output)

# COMMAND ----------

# MAGIC %md
# MAGIC # Test the agent
# MAGIC
# MAGIC Test the agent with memory and traces.

# COMMAND ----------

# #Uncomment below code to test agent. Change the remember and test to true to enable memory and run test messages 
# #Create the agent with the system message if it exists
# remember=False
# test=False


# config = ModelConfig(development_config="config.yml")
# prompt_details=config.get("agent_prompt")

# if remember:
#     memory=MemorySaver()
#     try:
#         system_message = prompt_details
#         agent_with_raw_output = create_react_agent(llm, all_tools, state_modifier=system_message
#                                                     ,checkpointer=memory
#                                                 )
#     except KeyError:
#         agent_with_raw_output = create_react_agent(llm, all_tools
#                                                 ,checkpointer=memory
#                                                 )
# else:
#     try:
#         system_message = prompt_details
#         agent_with_raw_output = create_react_agent(llm, all_tools, state_modifier=system_message
#                                                 )
#         #Check for agent_with_raw_output.step_timeout = 2 for timeout increase
#     except KeyError:
#         agent_with_raw_output = create_react_agent(llm, all_tools
#                                                 )

# agent = agent_with_raw_output | RunnableGenerator(wrap_output)


# if test:
#     import uuid
#     thread_id=uuid.uuid4()
#     config={ "configurable" : { "thread_id" : thread_id} }
#     print ("thread_id: ",thread_id)

#     message_list=["Hi",
#               "My Loyalty ID is L002. I am Alergic to Nuts",#Preferences
#               "Give me all the details of my offer",#Offers
#               "Suggest me a recipie which uses these offers",#Suggest on offers
#               "Yes, add all ingredients to my list. Suggest Weather appropriate products.", #Weather
#               " Yes, consider the festivals",#Festivals
#               "How to do milkshake? Add ingredients to list.",#"Recipe"
#               "Add Expiring Products",#"Expiring Products"
#               "Check for Availability and Price. Keep products even if they are not available.", #Availability
#               "Give me the summary of everything.", #Summary
#               "Send details over email"#Send email
#                         ] #Write down your message list ask per your prompt planning.

#     if remember:
#         for user_message in message_list:
#             input_message={"role": "user", "content": user_message}
#             response=agent.invoke({"messages": [input_message]},config=config)
#             print (response)
#             print ("\n ###### \n")
#     else:
#             response=agent.invoke({"messages": [message_list[0]]})

# COMMAND ----------

mlflow.models.set_model(agent)