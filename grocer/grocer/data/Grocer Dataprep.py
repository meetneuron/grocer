# Databricks notebook source
!pip install langchain_community
dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC This notebook creates a fictitious multinational grocery database.

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC # Catalog, Schema, LLM

# COMMAND ----------


# Define catalog, schema, and table names
catalog_name = "genai"
schema_name = "data"
endpoint="databricks-mixtral-8x7b-instruct"

# COMMAND ----------

from langchain_community.chat_models import ChatDatabricks
# Create the llm

llm = ChatDatabricks(endpoint=endpoint,temperature=0)

# COMMAND ----------

# MAGIC %md
# MAGIC # Generate Table Descriptions using AI
# MAGIC
# MAGIC This helps agent to get additional information when reading UC table schema. Databricks has a manual-UI based implementation in UC , but you may want a programatic way to do it. Here it is! :-) 

# COMMAND ----------

def get_table_column_descriptions(schema,catalog_name,schema_name,table_name,llm):
    import ast

    try:
        #Prompt asking LLM to generate comments for columns and tables
        input_string=f"""Generate descriptive information on columns. No need to mention datatype of the column in column descriptions. After that, based on generated column descriptions, generate the information on what any table containing these columns can be used for. 
        {str(schema)}
        Return should be in the format of list of dictionary like below.
        [{{"table": "table_description"}}, {{"Column1":"Column Description", "Column2":"Column2 Description"}}]
        """

        #Asking LLM to generate output.
        response=llm.invoke(input_string
        )
        
        #Extracting descriptions from output.
        table_description=ast.literal_eval(response.content)[0]['table']
        column_descriptions=ast.literal_eval(response.content)[1]

        #Adding comments at table level

        spark.sql(f""" ALTER TABLE {catalog_name}.{schema_name}.{table_name} SET TBLPROPERTIES ('comment' = "{table_description}") """)

        # Register column descriptions in Unity Catalog
        for column, description in column_descriptions.items():
            print (column,description)
            spark.sql(f""" ALTER TABLE {catalog_name}.{schema_name}.{table_name} ALTER COLUMN {column} COMMENT "{description}" """)

        return_value="Comments Added"
    except Exception as e:
        print (e)
        return_value=e 



    return return_value

# COMMAND ----------

# MAGIC %md
# MAGIC # Change Datafeed Function

# COMMAND ----------

from pyspark.sql.types import StructType, StructField, StringType
from pyspark.sql.functions import monotonically_increasing_id
from pyspark.sql.functions import concat_ws, col
from pyspark.sql import functions as F

# Enable Change Data Feed for the table
def enableChangeDataFeed(catalog_name,schema_name,table_name):
    alter_table_query = f"""ALTER TABLE {catalog_name}.{schema_name}.{table_name} SET TBLPROPERTIES (delta.enableChangeDataFeed = true)"""
    print (alter_table_query)
    return_value=spark.sql(alter_table_query)
    return return_value

# COMMAND ----------

# MAGIC %md
# MAGIC # Users Table

# COMMAND ----------



# Define the schema for the table
schema = StructType([
    StructField("LoyaltyID", StringType(), True),
    StructField("UserName", StringType(), True),
    StructField("UserEmail", StringType(), True),
    StructField("UserHomeStoreAddress", StringType(), True),
    StructField("StoreID", StringType(), True)
])

# Define the data for the table
#For demo we will set all user ID to one email ID which we have configured also as sender email ID.
data = [
    ("L001", "Canadian","redacted@mails", "150 Carlton, Toronto, Ontario, Canada", "5"),
    ("L002", "Indian","redacted@mails", "Vihar, Delhi, India", "11"),
    ("L003", "Arab","redacted@mails", "Financial Center Rd, Downtown Dubai, Dubai, United Arab Emirates", "21"),
    ("L004","Mexican" ,"redacted@mails", "104, Parliament, Mexico City, Mexico", "2")
]

# Create the DataFrame
users = spark.createDataFrame(data, schema)

table_name = "users"
# Save the DataFrame as a table in Unity Catalog
spark.sql(f"DROP TABLE IF EXISTS {catalog_name}.{schema_name}.{table_name}")

users.write.mode("overwrite").saveAsTable(f"{catalog_name}.{schema_name}.{table_name}")

get_table_column_descriptions(schema,catalog_name,schema_name,table_name,llm)

# Display the DataFrame
display(users)

# COMMAND ----------

# MAGIC %md
# MAGIC # Product Table

# COMMAND ----------

from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType

# Define the schema for the Grocery Product Database
grocery_product_schema = StructType([
    StructField("ProductID", StringType(), True),
    StructField("ProductName", StringType(), True),
    StructField("Units", IntegerType(), True),
    StructField("UnitOfMeasurement", StringType(), True),
    StructField("UnitPrice", DoubleType(), True)
])

# Define the data for the Grocery Product Database
grocery_product_data = [
    ("G001", "Milk", 1, "Liter",1.99),
    ("G002", "Bread Loaf",1,"Pack", 2.49),
    ("G003", "Apples",1,"Kg", 3.49),
    ("G004", "Bananas",1 ,"Kg", 0.99)
]

# Create the DataFrame for the Grocery Product Database
products = spark.createDataFrame(grocery_product_data, grocery_product_schema)

store_id=users.select(F.col('StoreID')).distinct()

products = products.crossJoin(store_id)

products = products.withColumn("ProductIDStoreId", F.concat(products.ProductID, F.lit("_"), products.StoreID))

table_name = "products"
# Save the DataFrame as a table in Unity Catalog
spark.sql(f"DROP TABLE IF EXISTS {catalog_name}.{schema_name}.{table_name}")

products.write.mode("overwrite").saveAsTable(f"{catalog_name}.{schema_name}.{table_name}")

grocery_product_schema=products.schema
get_table_column_descriptions(grocery_product_schema,catalog_name,schema_name,table_name,llm)

# Display the DataFrame
display(products)

# Define the table name and schema
enableChangeDataFeed(catalog_name,schema_name,table_name)

# COMMAND ----------

# MAGIC %md
# MAGIC # Transactions Table

# COMMAND ----------

from datetime import datetime
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DateType

# Define the schema for the Transactional Table
transaction_schema = StructType([
    StructField("TransactionID", StringType(), True),
    StructField("LoyaltyID", StringType(), True),
    StructField("ProductID", StringType(), True),
    StructField("QuantityPurchased", IntegerType(), True),
    StructField("ProductPurchaseDate", DateType(), True),
    StructField("ProductExpiryDate", DateType(), True)
])

# Define the data for the Transactional Table with dates converted to date objects
transaction_data = [
    ("T001", "L001", "G001", 2, datetime.strptime("2023-09-01", "%Y-%m-%d"), datetime.strptime("2023-09-10", "%Y-%m-%d")),
    ("T002", "L002", "G002", 1, datetime.strptime("2023-09-02", "%Y-%m-%d"), datetime.strptime("2023-09-09", "%Y-%m-%d")),
    ("T003", "L003", "G003", 3, datetime.strptime("2023-09-03", "%Y-%m-%d"), datetime.strptime("2023-09-12", "%Y-%m-%d")),
    ("T004", "L004", "G004", 2, datetime.strptime("2023-09-04", "%Y-%m-%d"), datetime.strptime("2023-09-11", "%Y-%m-%d"))
]

# Create the DataFrame for the Transactional Table
transactions = spark.createDataFrame(transaction_data, schema=transaction_schema)

# Display the DataFrame
display(transactions)

from pyspark.sql.functions import col

# Assuming grocery_product_df is defined elsewhere and includes a "ProductID" and "Price" column
# Join the transactional DataFrame with the grocery product DataFrame on ProductID to include the price
transactions = transactions.join(
    products,
    "ProductID"
).select(
    transactions.TransactionID,
    transactions.LoyaltyID,
    transactions.ProductID,
    products.ProductName,
    transactions.QuantityPurchased,
    transactions.ProductPurchaseDate,
    transactions.ProductExpiryDate,
    products.UnitPrice,
    (col("QuantityPurchased") * col("UnitPrice")).alias("TotalPrice")
)

transactions = transactions.join(
    users.select(['LoyaltyID','StoreID']),
    "LoyaltyID")

table_name = "transactions"
# Save the DataFrame as a table in Unity Catalog
spark.sql(f"DROP TABLE IF EXISTS {catalog_name}.{schema_name}.{table_name}")
transactions.write.mode("overwrite").saveAsTable(f"{catalog_name}.{schema_name}.{table_name}")

transaction_schema=transactions.schema
get_table_column_descriptions(transaction_schema,catalog_name,schema_name,table_name,llm)

# Display the DataFrame with price and total price included
display(transactions)

# COMMAND ----------

# MAGIC %md
# MAGIC # Recipe Data

# COMMAND ----------

from pyspark.sql.types import StructType, StructField, StringType, ArrayType

# Define the schema for the Recipes Database
recipe_schema = StructType([
    StructField("RecipeName", StringType(), True),
    StructField("Ingredients", ArrayType(StringType()), True),
    StructField("Steps", ArrayType(StringType()), True)
])

# Define the data for the Recipes Database
recipe_data = [
    ("Milkshake", ["Milk", "Bananas", "Sugar", "Ice cubes"], 
     ["Pour milk into a blender.", "Add sliced bananas and sugar.", "Blend until smooth.", "Serve with ice cubes."]),
    ("Fruit Salad", ["Apples", "Bananas", "Oranges", "Lemon juice"], 
     ["Chop all fruits into small pieces.", "Mix them in a large bowl.", "Drizzle with lemon juice.", "Serve chilled."]),
    ("Banana Bread", ["Bananas", "Flour", "Eggs", "Sugar", "Baking powder"], 
     ["Preheat oven to 175°C.", "Mash bananas.", "Mix all ingredients until well combined.", "Pour into a loaf pan and bake for 60 minutes."])
]

# Create the DataFrame for the Recipes Database
recipe = spark.createDataFrame(recipe_data, schema=recipe_schema)

recipe = recipe.withColumn("RecipieID", monotonically_increasing_id())

recipe = recipe.select("RecipieID", "RecipeName", "Ingredients", "Steps")

recipe = recipe.withColumn(
    "content", 
    concat_ws(". ", 
              concat_ws(": ", F.lit("Recipe"), F.col("RecipeName")),
              concat_ws(": ", F.lit("Ingredients"), F.concat_ws(", ", col("Ingredients"))),
              concat_ws(": ", F.lit("Steps"), F.concat_ws(" ", col("Steps")))
             )
)

table_name = "recipe"
# Save the DataFrame as a table in Unity Catalog
spark.sql(f"DROP TABLE IF EXISTS {catalog_name}.{schema_name}.{table_name}")
recipe.write.mode("overwrite").option("mergeSchema", "true").saveAsTable(f"{catalog_name}.{schema_name}.{table_name}")

recipe_schema=recipe.schema
get_table_column_descriptions(recipe_schema,catalog_name,schema_name,table_name,llm)

enableChangeDataFeed(catalog_name,schema_name,table_name)
# Display the DataFrame
display(recipe)

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC #Offers Data

# COMMAND ----------

from pyspark.sql.functions import lit, array, array_join, collect_list, when, rand, round, expr, current_date, date_add, explode

# Generate random product recommendations for each user
# Assuming each user is recommended 2 products randomly
offers = (users.join(products, how="cross")
                            .groupBy("LoyaltyID")
                            .agg(collect_list("ProductID").alias("RecommendedProducts"))
                            .withColumn("RecommendedProducts", expr("slice(RecommendedProducts, 1, 2)")))



# Assign the same products as recommendations for specific Loyalty IDs
offers = offers.withColumn("RecommendedProducts",
                                                             when(col("LoyaltyID").isin("L001", "L003"),
                                                                  array(lit("G001"), lit("G002")))
                                                             .when(col("LoyaltyID").isin("L002", "L004"),
                                                                   array(lit("G003"), lit("G004")))
                                                             .otherwise(col("RecommendedProducts")))

# Add the "OfferPoint" column with random values between 100 and 200
offers = offers.withColumn("OfferLoyaltyPoints", round(rand() * 100 + 100))

# Add Offer Start Date and Offer End Date
offers = offers.withColumn("OfferStartDate", current_date())
offers = offers.withColumn("OfferEndDate", date_add(current_date(), 7))

# Select the required columns
offers = offers.select(
    "LoyaltyID",
    "RecommendedProducts",
    "OfferLoyaltyPoints",
    "OfferStartDate",
    "OfferEndDate"
)

from pyspark.sql.functions import explode

# Split the list in RecommendedProducts into separate rows
offers = offers.withColumn("OfferedProductID", explode("RecommendedProducts"))

# Select the required columns
offers = offers.select(
    "LoyaltyID",
    "OfferedProductID",
    "OfferLoyaltyPoints",
    "OfferStartDate",
    "OfferEndDate"
)

product_decriptions = products.select(["ProductID", "ProductName"]).distinct()
offers = offers.join(product_decriptions, offers.OfferedProductID == product_decriptions.ProductID)
offers=offers.withColumnRenamed("Description", "ProductName")
offers=offers.drop("ProductID")
# offers.display()

table_name = "offers"
# Save the DataFrame as a table in Unity Catalog
spark.sql(f"DROP TABLE IF EXISTS {catalog_name}.{schema_name}.{table_name}")
offers.write.mode("overwrite").saveAsTable(f"{catalog_name}.{schema_name}.{table_name}")

schema=offers.schema
get_table_column_descriptions(schema,catalog_name,schema_name,table_name,llm)

# Display the DataFrame
display(offers)