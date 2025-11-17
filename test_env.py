from dotenv import load_dotenv
import os

load_dotenv()

print("DB Host:", os.getenv("DB_HOST"))
print("DB Name:", os.getenv("DB_NAME"))
print("DB User:", os.getenv("DB_USER"))