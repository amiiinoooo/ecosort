import os
#config.py
# MySQL Database Configuration
MYSQL_HOST = 'localhost'  # The address of the MySQL server (localhost means it's on the same machine)
MYSQL_USER = 'root'  # The username used to connect to MySQL
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')  # set in your environment, never commit it
MYSQL_DB = 'smartbin_db'  # The name of the database to use in MySQL
MYSQL_CURSORCLASS = 'DictCursor'  # Ensures that the results returned by the query are in dictionary format (key-value pairs)

# Blynk Authentication Token
BLYNK_AUTH = "YOUR_BLYNK_AUTH_TOKEN"  # The token used to authenticate your Blynk application for controlling IoT devices

# Fill Level Threshold
THRESHOLD = 90  # The fill level threshold percentage 

