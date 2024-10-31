# Databricks notebook source
# MAGIC %md
# MAGIC
# MAGIC # We have kept the databricks auto generated driver notebook as is for the teams which may want to refer the key links here.

# COMMAND ----------

# MAGIC %md
# MAGIC # Driver notebook
# MAGIC
# MAGIC This is an auto-generated notebook created by an AI Playground export. We generated three notebooks in the same folder:
# MAGIC - [agent]($./agent): contains the code to build the agent.
# MAGIC - [config.yml]($./config.yml): contains the configurations.
# MAGIC - [**driver**]($./driver): logs, evaluate, registers, and deploys the agent.
# MAGIC
# MAGIC This notebook uses Mosaic AI Agent Framework ([AWS](https://docs.databricks.com/en/generative-ai/retrieval-augmented-generation.html) | [Azure](https://learn.microsoft.com/en-us/azure/databricks/generative-ai/retrieval-augmented-generation)) to deploy the agent defined in the [agent]($./agent) notebook. The notebook does the following:
# MAGIC 1. Logs the agent to MLflow
# MAGIC 2. Evaluate the agent with Agent Evaluation
# MAGIC 3. Registers the agent to Unity Catalog
# MAGIC 4. Deploys the agent to a Model Serving endpoint
# MAGIC
# MAGIC ## Prerequisities
# MAGIC
# MAGIC - Address all `TODO`s in this notebook.
# MAGIC - Review the contents of [config.yml]($./config.yml) as it defines the tools available to your agent, the LLM endpoint, and the agent prompt.
# MAGIC - Review and run the [agent]($./agent) notebook in this folder to view the agent's code, iterate on the code, and test outputs.
# MAGIC
# MAGIC ## Next steps
# MAGIC
# MAGIC After your agent is deployed, you can chat with it in AI playground to perform additional checks, share it with SMEs in your organization for feedback, or embed it in a production application. See docs ([AWS](https://docs.databricks.com/en/generative-ai/deploy-agent.html) | [Azure](https://learn.microsoft.com/en-us/azure/databricks/generative-ai/deploy-agent)) for details

# COMMAND ----------

# MAGIC %pip install -U -qqqq databricks-agents mlflow langchain==0.2.16 langgraph-checkpoint==1.0.12  langchain_core langchain-community==0.2.16 langgraph==0.2.16 pydantic databricks-sql-connector databricks-vectorsearch geopy meteostat
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

#geopy meteostat

# COMMAND ----------

# from databricks import agents
# help(agents.deploy)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Log the `agent` as an MLflow model
# MAGIC Log the agent as code from the [agent]($./agent) notebook. See [MLflow - Models from Code](https://mlflow.org/docs/latest/models.html#models-from-code).

# COMMAND ----------

# Log the model to MLflow
import os
import mlflow
import uuid
from mlflow.models import infer_signature


input_example ={
    "messages": [
        {
            "role": "user",
            "content": "Hi"
        }]
    }

with mlflow.start_run():
    logged_agent_info = mlflow.langchain.log_model(
        lc_model=os.path.join(
            os.getcwd(),
            'grocer_agent',
        ),
        pip_requirements=[
            f"langchain==0.2.16",
            f"langchain-community==0.2.16",
            f"langgraph-checkpoint==1.0.12",
            f"langgraph==0.2.16",
            f"pydantic",
            f"databricks-sql-connector",
            f"databricks-vectorsearch",
            f"geopy", 
            f"meteostat"
        ],
        model_config="config.yml",
        artifact_path='agent',
        #signature=signature
        input_example=input_example
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Evaluate the agent with [Agent Evaluation](https://learn.microsoft.com/azure/databricks/generative-ai/agent-evaluation/)
# MAGIC
# MAGIC You can edit the requests or expected responses in your evaluation dataset and run evaluation as you iterate your agent, leveraging mlflow to track the computed quality metrics.

# COMMAND ----------

# import pandas as pd

# eval_examples = [
#     {
#         "request": {
#             "messages": [
#                 {
#                     "role": "user",
#                     "content": "What is the email ID for L004?"
#                 }
#             ]
#         },
#         "expected_response": "user1@example.com"
#     }
# ]

# eval_dataset = pd.DataFrame(eval_examples)
# display(eval_dataset)

# COMMAND ----------

# import mlflow
# import pandas as pd

# with mlflow.start_run(run_id=logged_agent_info.run_id):
#     eval_results = mlflow.evaluate(
#         f"runs:/{logged_agent_info.run_id}/agent",  # replace `chain` with artifact_path that you used when calling log_model.
#         data=eval_dataset,  # Your evaluation dataset
#         model_type="databricks-agent",  # Enable Mosaic AI Agent Evaluation
#     )

# # Review the evaluation results in the MLFLow UI (see console output), or access them in place:
# display(eval_results.tables['eval_results'])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Register the model to Unity Catalog
# MAGIC
# MAGIC Update the `catalog`, `schema`, and `model_name` below to register the MLflow model to Unity Catalog.

# COMMAND ----------

mlflow.set_registry_uri("databricks-uc")

# TODO: define the catalog, schema, and model name for your UC model
catalog = "genai"
schema = "llm"
model_name = "grocer"
UC_MODEL_NAME = f"{catalog}.{schema}.{model_name}"

# register the model to UC
uc_registered_model_info = mlflow.register_model(model_uri=logged_agent_info.model_uri, name=UC_MODEL_NAME)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Deploy the agent

# COMMAND ----------

from databricks import agents
help(agents.deploy)

# COMMAND ----------

# # Deploy the model to the review app and a model serving endpoint
agents.deploy(UC_MODEL_NAME, uc_registered_model_info.version,scale_to_zero=True)